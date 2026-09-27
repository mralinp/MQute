"""Handler signature analysis and dependency injection.

Every handler (and every dependency) is analysed once, when it is registered,
into a :class:`Dependant`. At dispatch time the dependant resolves each
parameter from the incoming message:

* a parameter named like a topic parameter receives that value, converted to
  its annotation (``int``, ``float``, ``bool`` or ``str``);
* a parameter annotated with :class:`~mqute.Message` receives the message;
* a parameter declared with :class:`Depends` receives the dependency's result;
* the one remaining parameter, if any, receives the decoded payload.
"""

from __future__ import annotations

import asyncio
import inspect
import typing
from collections.abc import Callable
from contextlib import AsyncExitStack, asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from typing import Any, Protocol

from .encoding import convert_text, decode
from .message import Message


class Depends:
    """Declare a dependency, FastAPI style.

    ``def handler(db = Depends(get_db))`` or
    ``def handler(db: Annotated[Database, Depends(get_db)])``.

    Dependencies may be sync or async functions, or (async) generators whose
    code after ``yield`` runs once the handler has finished. Results are
    cached per message unless ``use_cache=False``.
    """

    __slots__ = ("dependency", "use_cache")

    def __init__(self, dependency: Callable[..., Any], *, use_cache: bool = True) -> None:
        self.dependency = dependency
        self.use_cache = use_cache

    def __repr__(self) -> str:
        return f"Depends({getattr(self.dependency, '__name__', self.dependency)!r})"


@dataclass
class Context:
    """Per-message state shared by every resolver."""

    message: Message
    params: dict[str, str]
    stack: AsyncExitStack
    cache: dict[Callable[..., Any], Any] = field(default_factory=dict)


class _Resolver(Protocol):
    async def resolve(self, context: Context) -> Any: ...


@dataclass(frozen=True)
class _TopicParam:
    name: str
    annotation: Any

    async def resolve(self, context: Context) -> Any:
        return convert_text(context.params[self.name], self.annotation)


class _MessageParam:
    async def resolve(self, context: Context) -> Any:
        return context.message


@dataclass(frozen=True)
class _PayloadParam:
    annotation: Any

    async def resolve(self, context: Context) -> Any:
        return decode(context.message.payload, self.annotation)


@dataclass(frozen=True)
class _DependencyParam:
    dependant: Dependant
    use_cache: bool

    async def resolve(self, context: Context) -> Any:
        key = self.dependant.call
        if self.use_cache and key in context.cache:
            return context.cache[key]
        value = await self.dependant.run(context)
        if self.use_cache:
            context.cache[key] = value
        return value


class Dependant:
    """A callable together with the resolvers for its parameters."""

    def __init__(self, call: Callable[..., Any], topic_params: tuple[str, ...], *, is_handler: bool = False) -> None:
        self.call = call
        self._is_handler = is_handler
        self._resolvers = _build_resolvers(call, topic_params)

    async def run(self, context: Context) -> Any:
        kwargs = {name: await resolver.resolve(context) for name, resolver in self._resolvers.items()}
        call = self.call
        if inspect.isasyncgenfunction(call):
            return await context.stack.enter_async_context(asynccontextmanager(call)(**kwargs))
        if inspect.isgeneratorfunction(call):
            return context.stack.enter_context(contextmanager(call)(**kwargs))
        if _is_async(call):
            return await call(**kwargs)
        if self._is_handler:
            # Blocking handlers must not stall the event loop.
            return await asyncio.to_thread(call, **kwargs)
        return call(**kwargs)


def _build_resolvers(call: Callable[..., Any], topic_params: tuple[str, ...]) -> dict[str, _Resolver]:
    hints = _type_hints(call)
    resolvers: dict[str, _Resolver] = {}
    payload_name: str | None = None
    for param in inspect.signature(call).parameters.values():
        if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD, param.POSITIONAL_ONLY):
            raise TypeError(f"{_label(call)}: parameter {param.name!r} must be a regular or keyword parameter")
        annotation = hints.get(param.name, param.empty)
        depends = _find_depends(param, annotation)
        if depends is not None:
            dependant = Dependant(depends.dependency, topic_params)
            resolvers[param.name] = _DependencyParam(dependant, depends.use_cache)
        elif param.name in topic_params:
            resolvers[param.name] = _TopicParam(param.name, _unwrap(annotation))
        elif _unwrap(annotation) is Message:
            resolvers[param.name] = _MessageParam()
        elif payload_name is None:
            payload_name = param.name
            resolvers[param.name] = _PayloadParam(annotation)
        else:
            raise TypeError(
                f"{_label(call)}: only one payload parameter is allowed, found {payload_name!r} and "
                f"{param.name!r}. Did you misspell a topic parameter?"
            )
    return resolvers


def _find_depends(param: inspect.Parameter, annotation: Any) -> Depends | None:
    if isinstance(param.default, Depends):
        return param.default
    if typing.get_origin(annotation) is typing.Annotated:
        return next((meta for meta in annotation.__metadata__ if isinstance(meta, Depends)), None)
    return None


def _type_hints(call: Callable[..., Any]) -> dict[str, Any]:
    if inspect.isclass(call):
        target: Any = call.__init__
    elif inspect.isfunction(call) or inspect.ismethod(call):
        target = call
    else:
        target = type(call).__call__
    try:
        return typing.get_type_hints(target, include_extras=True)
    except Exception as exc:
        raise TypeError(f"{_label(call)}: cannot resolve type annotations ({exc})") from exc


def _unwrap(annotation: Any) -> Any:
    if typing.get_origin(annotation) is typing.Annotated:
        return typing.get_args(annotation)[0]
    return annotation


def _is_async(call: Callable[..., Any]) -> bool:
    return inspect.iscoroutinefunction(call) or inspect.iscoroutinefunction(type(call).__call__)


def _label(call: Callable[..., Any]) -> str:
    return getattr(call, "__qualname__", repr(call))
