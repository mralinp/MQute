"""The MQute application: routing, lifecycle and the message pipeline."""

from __future__ import annotations

import asyncio
import contextlib
import inspect
import logging
import os
import signal
import types
from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager, AsyncExitStack
from typing import Any, TypeVar

from .broker import Broker
from .dependencies import Context
from .encoding import encode
from .message import Message
from .response import Response
from .routing import CallNext, Middleware, Route, Router, Subscription
from .topics import validate_topic
from .transport import PahoTransport, Transport, TransportEvents

logger = logging.getLogger("mqute")

BROKER_URL_ENV = "MQUTE_BROKER_URL"

Hook = Callable[..., Any]
HookT = TypeVar("HookT", bound=Hook)
ExceptionHandler = Callable[[Message, Exception], Any]
ExceptionHandlerT = TypeVar("ExceptionHandlerT", bound=ExceptionHandler)
Lifespan = Callable[["MQute"], AbstractAsyncContextManager[Any]]


class MQute(Router):
    """An MQTT application, in the spirit of FastAPI.

    >>> app = MQute("mqtt://localhost:1883")
    >>> @app.subscribe("sensors/{sensor_id}/temperature")
    ... async def temperature(sensor_id: str, celsius: float) -> None: ...
    >>> app.run()  # doctest: +SKIP

    ``broker`` is a :class:`Broker`, a broker URL, or ``None`` to read the URL
    from the ``MQUTE_BROKER_URL`` environment variable (default
    ``mqtt://localhost``). Pass ``transport`` to use a custom MQTT client.
    """

    def __init__(
        self,
        broker: Broker | str | None = None,
        *,
        transport: Transport | None = None,
        lifespan: Lifespan | None = None,
        prefix: str = "",
        shutdown_timeout: float = 10.0,
    ) -> None:
        super().__init__(prefix=prefix)
        self.broker = _resolve_broker(broker)
        self.transport = transport or PahoTransport(self.broker)
        self.shutdown_timeout = shutdown_timeout
        self.state = types.SimpleNamespace()  # a place for app-wide resources
        self._lifespan = lifespan
        self._startup_hooks: list[Hook] = []
        self._shutdown_hooks: list[Hook] = []
        self._connect_hooks: list[Hook] = []
        self._disconnect_hooks: list[Hook] = []
        self._exception_handlers: dict[type[Exception], ExceptionHandler] = {}
        self._tasks: set[asyncio.Task[None]] = set()
        self._stack: AsyncExitStack | None = None
        self._accepting = False

    # -- hooks ---------------------------------------------------------------

    def on_startup(self, hook: HookT) -> HookT:
        """Run ``hook()`` before connecting to the broker."""
        self._startup_hooks.append(hook)
        return hook

    def on_shutdown(self, hook: HookT) -> HookT:
        """Run ``hook()`` after disconnecting from the broker."""
        self._shutdown_hooks.append(hook)
        return hook

    def on_connect(self, hook: HookT) -> HookT:
        """Run ``hook()`` after every successful (re)connection."""
        self._connect_hooks.append(hook)
        return hook

    def on_disconnect(self, hook: HookT) -> HookT:
        """Run ``hook(reason)`` when the connection drops; ``reason`` is ``None`` for a clean disconnect."""
        self._disconnect_hooks.append(hook)
        return hook

    def exception_handler(self, exc_type: type[Exception]) -> Callable[[ExceptionHandlerT], ExceptionHandlerT]:
        """Handle ``exc_type`` raised while processing a message.

        The handler is called as ``handler(message, exc)``; a non-``None``
        return value is published as the reply, just like a route's result.
        """

        def decorator(handler: ExceptionHandlerT) -> ExceptionHandlerT:
            self._exception_handlers[exc_type] = handler
            return handler

        return decorator

    # -- lifecycle -----------------------------------------------------------

    @property
    def is_running(self) -> bool:
        return self._stack is not None

    async def start(self) -> None:
        """Run startup hooks, connect and subscribe to every route."""
        if self._stack is not None:
            raise RuntimeError("MQute is already running")
        stack = AsyncExitStack()
        try:
            if self._lifespan is not None:
                await stack.enter_async_context(self._lifespan(self))
            stack.push_async_callback(self._run_hooks, self._shutdown_hooks)
            await self._run_hooks(self._startup_hooks)
            events = TransportEvents(self._on_message, self._on_connect, self._on_disconnect)
            await self.transport.connect(self.subscriptions(), events)
            # Unwound in reverse: finish in-flight messages, disconnect, then
            # let the disconnect hooks run before the shutdown hooks.
            stack.push_async_callback(self._drain)
            stack.push_async_callback(self.transport.disconnect)
            stack.push_async_callback(self._drain)
            self._accepting = True
        except BaseException:
            await stack.aclose()
            raise
        self._stack = stack

    async def stop(self) -> None:
        """Finish in-flight messages, disconnect and run shutdown hooks."""
        stack, self._stack = self._stack, None
        if stack is not None:
            await stack.aclose()

    async def __aenter__(self) -> MQute:
        await self.start()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.stop()

    async def serve(self) -> None:
        """Run until SIGINT/SIGTERM or until the task is cancelled."""
        async with self:
            await _wait_for_shutdown_signal()

    def run(self) -> None:
        """Blocking entry point: ``app.run()``."""
        with contextlib.suppress(KeyboardInterrupt):
            asyncio.run(self.serve())

    def subscriptions(self) -> list[Subscription]:
        """One subscription per distinct topic filter, at the highest requested QoS."""
        qos_by_topic: dict[str, int] = {}
        for route in self.routes:
            sub = route.subscription
            qos_by_topic[sub.topic] = max(sub.qos, qos_by_topic.get(sub.topic, 0))
        return [Subscription(topic, qos) for topic, qos in qos_by_topic.items()]

    # -- messaging -----------------------------------------------------------

    async def publish(
        self,
        topic: str,
        payload: Any = None,
        *,
        qos: int = 0,
        retain: bool = False,
        response_topic: str | None = None,
        correlation_data: bytes | None = None,
        content_type: str | None = None,
        user_properties: tuple[tuple[str, str], ...] = (),
    ) -> None:
        """Publish ``payload`` (bytes, str, JSON-able, dataclass or pydantic model)."""
        validate_topic(topic)
        await self.transport.publish(
            Message(
                topic=topic,
                payload=encode(payload),
                qos=qos,
                retain=retain,
                response_topic=response_topic,
                correlation_data=correlation_data,
                content_type=content_type,
                user_properties=user_properties,
            )
        )

    async def process(self, message: Message) -> None:
        """Route one message through middleware and its handler, and publish the reply.

        Exceptions without a registered exception handler propagate.
        """
        matched = self.match(message.topic)
        if matched is None:
            logger.debug("No route for topic %r", message.topic)
            return
        route, params = matched
        try:
            result = await self._call_route(route, params, message)
        except Exception as exc:
            handler = self._find_exception_handler(exc)
            if handler is None:
                raise
            result = await _call(handler, message, exc)
        await self._reply(result, message, route.response_topic_for(params))

    async def _call_route(self, route: Route, params: dict[str, str], message: Message) -> Any:
        async def endpoint(current: Message) -> Any:
            async with AsyncExitStack() as stack:
                return await route.dependant.run(Context(current, params, stack))

        call_next: CallNext = endpoint
        for middleware in reversed(route.middlewares):
            call_next = _chain(middleware, call_next)
        return await call_next(message)

    async def _reply(self, result: Any, request: Message, default_topic: str | None) -> None:
        if result is None:
            return
        reply = result if isinstance(result, Response) else Response(result)
        topic = reply.topic or request.response_topic or default_topic
        if topic is None:
            logger.warning("Handler for %r returned a value but no response topic is known", request.topic)
            return
        await self.publish(
            topic,
            reply.payload,
            qos=reply.qos,
            retain=reply.retain,
            correlation_data=request.correlation_data,
            content_type=reply.content_type,
            user_properties=reply.user_properties,
        )

    def _find_exception_handler(self, exc: Exception) -> ExceptionHandler | None:
        for cls in type(exc).__mro__:
            if cls in self._exception_handlers:
                return self._exception_handlers[cls]
        return None

    # -- transport callbacks (event loop thread) ----------------------------

    def _on_message(self, message: Message) -> None:
        if self._accepting:
            self._spawn(self._process_safely(message))

    def _on_connect(self) -> None:
        logger.info("Connected to %s:%s", self.broker.host, self.broker.resolved_port)
        self._spawn(self._run_hooks(self._connect_hooks))

    def _on_disconnect(self, reason: str | None) -> None:
        if reason:
            logger.warning("Disconnected from broker: %s", reason)
        self._spawn(self._run_hooks(self._disconnect_hooks, reason))

    async def _process_safely(self, message: Message) -> None:
        try:
            await self.process(message)
        except Exception:
            logger.exception("Unhandled error while processing message on %r", message.topic)

    def _spawn(self, coroutine: Awaitable[None]) -> None:
        task = asyncio.ensure_future(coroutine)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _drain(self) -> None:
        self._accepting = False
        if not self._tasks:
            return
        _, pending = await asyncio.wait(set(self._tasks), timeout=self.shutdown_timeout)
        for task in pending:
            task.cancel()
        if pending:
            logger.warning("Cancelled %d message handler(s) still running at shutdown", len(pending))

    async def _run_hooks(self, hooks: list[Hook], *args: Any) -> None:
        for hook in hooks:
            await _call(hook, *args)


def _resolve_broker(broker: Broker | str | None) -> Broker:
    if isinstance(broker, Broker):
        return broker
    return Broker.from_url(broker or os.environ.get(BROKER_URL_ENV, "mqtt://localhost"))


def _chain(middleware: Middleware, call_next: CallNext) -> CallNext:
    async def call(message: Message) -> Any:
        return await middleware(message, call_next)

    return call


async def _call(func: Callable[..., Any], *args: Any) -> Any:
    result = func(*args)
    if inspect.isawaitable(result):
        return await result
    return result


async def _wait_for_shutdown_signal() -> None:
    loop = asyncio.get_running_loop()
    stop = asyncio.Event()
    installed: list[signal.Signals] = []
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
            installed.append(sig)
        except (NotImplementedError, RuntimeError):  # Windows, or not the main thread
            pass
    try:
        await stop.wait()
    finally:
        for sig in installed:
            loop.remove_signal_handler(sig)
