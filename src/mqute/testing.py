"""Test utilities: exercise an app without a broker, like FastAPI's ``TestClient``."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any

from .app import MQute
from .encoding import encode
from .exceptions import PublishError
from .message import Message
from .routing import Subscription
from .transport import Transport, TransportEvents


class MemoryTransport(Transport):
    """A broker-less transport that records everything the app publishes."""

    def __init__(self) -> None:
        self.published: list[Message] = []
        self.subscriptions: list[Subscription] = []
        self.connected = False
        self._events: TransportEvents | None = None

    async def connect(self, subscriptions: Sequence[Subscription], events: TransportEvents) -> None:
        self.subscriptions = list(subscriptions)
        self.connected = True
        self._events = events
        events.on_connect()

    async def disconnect(self) -> None:
        if self.connected and self._events is not None:
            self.connected = False
            self._events.on_disconnect(None)

    async def publish(self, message: Message) -> None:
        if not self.connected:
            raise PublishError("Not connected")
        self.published.append(message)


class TestClient:
    """Drive an :class:`~mqute.MQute` app synchronously in tests.

    >>> with TestClient(app) as client:  # doctest: +SKIP
    ...     replies = client.publish("sensors/1/temperature", 21.5)

    Startup/shutdown hooks run on enter/exit, and exceptions raised by
    handlers propagate to the test.
    """

    __test__ = False  # not a pytest test class

    def __init__(self, app: MQute) -> None:
        self.app = app
        self.transport = MemoryTransport()
        self._original_transport: Transport | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    def __enter__(self) -> TestClient:
        self._original_transport, self.app.transport = self.app.transport, self.transport
        self._loop = asyncio.new_event_loop()
        try:
            self._loop.run_until_complete(self.app.start())
        except BaseException:
            self._close()
            raise
        return self

    def __exit__(self, *_: object) -> None:
        try:
            self._require_loop().run_until_complete(self.app.stop())
        finally:
            self._close()

    @property
    def published(self) -> list[Message]:
        """Every message the app has published so far."""
        return self.transport.published

    def publish(
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
    ) -> list[Message]:
        """Deliver a message to the app and return the messages it published in response."""
        loop = self._require_loop()
        message = Message(
            topic=topic,
            payload=encode(payload),
            qos=qos,
            retain=retain,
            response_topic=response_topic,
            correlation_data=correlation_data,
            content_type=content_type,
            user_properties=user_properties,
        )
        already_published = len(self.published)
        loop.run_until_complete(self.app.process(message))
        return self.published[already_published:]

    def _require_loop(self) -> asyncio.AbstractEventLoop:
        if self._loop is None:
            raise RuntimeError("Use TestClient as a context manager: `with TestClient(app) as client:`")
        return self._loop

    def _close(self) -> None:
        if self._original_transport is not None:
            self.app.transport = self._original_transport
            self._original_transport = None
        if self._loop is not None:
            self._loop.close()
            self._loop = None
