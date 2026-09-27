"""Routers group handlers under a common topic prefix and middleware stack."""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, TypeVar

from .dependencies import Dependant
from .exceptions import TopicError
from .message import Message
from .topics import TopicPattern, join_topics, template_fields

Handler = Callable[..., Any]
CallNext = Callable[[Message], Awaitable[Any]]
Middleware = Callable[[Message, CallNext], Awaitable[Any]]
HandlerT = TypeVar("HandlerT", bound=Handler)
MiddlewareT = TypeVar("MiddlewareT", bound=Middleware)

_QOS_LEVELS = (0, 1, 2)


@dataclass(frozen=True)
class Subscription:
    """A topic filter the client subscribes to, with its requested QoS."""

    topic: str
    qos: int = 0


@dataclass(frozen=True)
class Route:
    """A handler bound to a topic pattern."""

    pattern: TopicPattern
    handler: Handler
    dependant: Dependant
    qos: int
    response_topic: str | None
    share_group: str | None
    middleware_stacks: tuple[list[Middleware], ...]

    @property
    def subscription(self) -> Subscription:
        topic = self.pattern.filter
        if self.share_group:
            topic = f"$share/{self.share_group}/{topic}"
        return Subscription(topic, self.qos)

    @property
    def middlewares(self) -> list[Middleware]:
        return [middleware for stack in self.middleware_stacks for middleware in stack]

    def response_topic_for(self, params: dict[str, str]) -> str | None:
        if self.response_topic is None:
            return None
        return self.response_topic.format(**params)


class Router:
    """A group of topic handlers, FastAPI's ``APIRouter`` for MQTT.

    >>> router = Router(prefix="devices")
    >>> @router.subscribe("{device_id}/status")
    ... async def status(device_id: str, payload: dict) -> None: ...
    """

    def __init__(self, prefix: str = "") -> None:
        self.prefix = prefix
        self.routes: list[Route] = []
        self._middlewares: list[Middleware] = []

    def subscribe(
        self,
        topic: str,
        *,
        qos: int = 0,
        response_topic: str | None = None,
        share_group: str | None = None,
    ) -> Callable[[HandlerT], HandlerT]:
        """Register the decorated function as the handler for ``topic``.

        ``response_topic`` is where non-``None`` return values are published
        when the incoming message carries no MQTT 5 response topic. It may use
        the topic parameters, e.g. ``"devices/{device_id}/ack"``.
        ``share_group`` turns the route into an MQTT 5 shared subscription
        (``$share/<group>/<topic>``) so several instances can split the load.
        """

        def decorator(handler: HandlerT) -> HandlerT:
            self.add_route(topic, handler, qos=qos, response_topic=response_topic, share_group=share_group)
            return handler

        return decorator

    def add_route(
        self,
        topic: str,
        handler: Handler,
        *,
        qos: int = 0,
        response_topic: str | None = None,
        share_group: str | None = None,
    ) -> Route:
        """Register ``handler`` for ``topic``; the non-decorator form of :meth:`subscribe`."""
        if qos not in _QOS_LEVELS:
            raise ValueError(f"QoS must be 0, 1 or 2, got {qos!r}")
        pattern = TopicPattern(self._full_topic(topic))
        _check_response_topic(response_topic, pattern)
        route = Route(
            pattern=pattern,
            handler=handler,
            dependant=Dependant(handler, pattern.params, is_handler=True),
            qos=qos,
            response_topic=response_topic,
            share_group=share_group,
            middleware_stacks=(self._middlewares,),
        )
        self.routes.append(route)
        return route

    def middleware(self, middleware: MiddlewareT) -> MiddlewareT:
        """Register an ``async def middleware(message, call_next)`` for this router's routes.

        Call ``await call_next(message)`` to continue to the handler; its
        return value is the handler's result. Skipping ``call_next`` drops the
        message.
        """
        _ensure_async(middleware)
        self._middlewares.append(middleware)
        return middleware

    def include_router(self, router: Router, *, prefix: str = "") -> None:
        """Copy every route of ``router`` into this router under ``prefix``.

        Routes are copied at call time, so register a router's handlers before
        including it. Middlewares stay live: adding one later still applies.
        """
        outer_prefix = join_topics(self.prefix, prefix)
        for route in router.routes:
            pattern = TopicPattern(join_topics(outer_prefix, route.pattern.pattern)) if outer_prefix else route.pattern
            self.routes.append(
                Route(
                    pattern=pattern,
                    handler=route.handler,
                    dependant=Dependant(route.handler, pattern.params, is_handler=True),
                    qos=route.qos,
                    response_topic=route.response_topic,
                    share_group=route.share_group,
                    middleware_stacks=(self._middlewares, *route.middleware_stacks),
                )
            )

    def match(self, topic: str) -> tuple[Route, dict[str, str]] | None:
        """Return the first route matching ``topic`` and its parameters."""
        for route in self.routes:
            params = route.pattern.match(topic)
            if params is not None:
                return route, params
        return None

    def _full_topic(self, topic: str) -> str:
        return join_topics(self.prefix, topic) if self.prefix else topic


def _ensure_async(middleware: Middleware) -> None:
    if not inspect.iscoroutinefunction(middleware):
        raise TypeError("Middleware must be an async function: async def mw(message, call_next)")


def _check_response_topic(response_topic: str | None, pattern: TopicPattern) -> None:
    if response_topic is None:
        return
    unknown = template_fields(response_topic) - set(pattern.params)
    if unknown:
        raise TopicError(f"response_topic {response_topic!r} uses unknown parameters: {sorted(unknown)}")
