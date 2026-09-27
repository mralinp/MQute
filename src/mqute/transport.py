"""The boundary between MQute and an MQTT client library.

MQute talks to brokers only through :class:`Transport`. The default
implementation, :class:`PahoTransport`, wraps ``paho-mqtt``; tests use
:class:`~mqute.testing.MemoryTransport`. Implement :class:`Transport` to plug
in any other client.
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion
from paho.mqtt.packettypes import PacketTypes
from paho.mqtt.properties import Properties

from .broker import Broker
from .exceptions import PublishError
from .message import Message
from .routing import Subscription

logger = logging.getLogger("mqute")


@dataclass(frozen=True)
class TransportEvents:
    """Callbacks a transport invokes, always on the event loop thread."""

    on_message: Callable[[Message], None]
    on_connect: Callable[[], None]
    on_disconnect: Callable[[str | None], None]


class Transport(ABC):
    """An MQTT connection, seen from MQute."""

    @abstractmethod
    async def connect(self, subscriptions: Sequence[Subscription], events: TransportEvents) -> None:
        """Connect, subscribe, and keep ``subscriptions`` alive across reconnects.

        Returns once the first connection is established; raises
        :class:`ConnectionError` if it cannot be.
        """

    @abstractmethod
    async def disconnect(self) -> None:
        """Close the connection. Must be safe to call when not connected."""

    @abstractmethod
    async def publish(self, message: Message) -> None:
        """Hand ``message`` over for delivery to the broker."""


class PahoTransport(Transport):
    """:class:`Transport` backed by ``paho-mqtt`` running its network loop in a thread."""

    def __init__(self, broker: Broker) -> None:
        self.broker = broker
        self._client: mqtt.Client | None = None

    @property
    def client(self) -> mqtt.Client | None:
        """The underlying paho client while connected, for advanced use."""
        return self._client

    async def connect(self, subscriptions: Sequence[Subscription], events: TransportEvents) -> None:
        if self._client is not None:
            raise RuntimeError("Transport is already connected")
        loop = asyncio.get_running_loop()
        first_connection: asyncio.Future[None] = loop.create_future()
        client = self._create_client()

        def settle(error: Exception | None) -> None:
            if first_connection.done():
                return
            if error is None:
                first_connection.set_result(None)
            else:
                first_connection.set_exception(error)

        def on_connect(client: mqtt.Client, _: Any, __: Any, reason_code: Any, ___: Any) -> None:
            if reason_code.is_failure:
                loop.call_soon_threadsafe(settle, ConnectionRefusedError(f"Broker refused connection: {reason_code}"))
                return
            if subscriptions:
                client.subscribe([(sub.topic, sub.qos) for sub in subscriptions])
            loop.call_soon_threadsafe(settle, None)
            loop.call_soon_threadsafe(events.on_connect)

        def on_connect_fail(_: mqtt.Client, __: Any) -> None:
            error = ConnectionError(f"Cannot reach broker at {self.broker.host}:{self.broker.resolved_port}")
            loop.call_soon_threadsafe(settle, error)

        def on_disconnect(_: mqtt.Client, __: Any, ___: Any, reason_code: Any, ____: Any) -> None:
            reason = None if reason_code is None or not reason_code.is_failure else str(reason_code)
            loop.call_soon_threadsafe(events.on_disconnect, reason)

        def on_message(_: mqtt.Client, __: Any, message: mqtt.MQTTMessage) -> None:
            loop.call_soon_threadsafe(events.on_message, _to_message(message))

        client.on_connect = on_connect
        client.on_connect_fail = on_connect_fail
        client.on_disconnect = on_disconnect
        client.on_message = on_message

        broker = self.broker
        connect_options: dict[str, Any] = {"keepalive": broker.keepalive}
        if self._is_v5:
            connect_options["clean_start"] = broker.clean_start
        client.connect_async(broker.host, broker.resolved_port, **connect_options)
        client.loop_start()
        self._client = client
        try:
            await asyncio.wait_for(first_connection, broker.connect_timeout)
        except BaseException as exc:
            await self.disconnect()
            if isinstance(exc, asyncio.TimeoutError):
                raise ConnectionError(f"Timed out connecting to {broker.host}:{broker.resolved_port}") from exc
            raise

    async def disconnect(self) -> None:
        client, self._client = self._client, None
        if client is None:
            return
        client.disconnect()
        await asyncio.to_thread(client.loop_stop)

    async def publish(self, message: Message) -> None:
        if self._client is None:
            raise PublishError("Not connected")
        info = self._client.publish(
            message.topic,
            message.payload,
            qos=message.qos,
            retain=message.retain,
            properties=self._publish_properties(message),
        )
        queued_for_reconnect = info.rc == mqtt.MQTT_ERR_NO_CONN and message.qos > 0
        if info.rc != mqtt.MQTT_ERR_SUCCESS and not queued_for_reconnect:
            raise PublishError(f"Publishing to {message.topic!r} failed: {mqtt.error_string(info.rc)}")

    @property
    def _is_v5(self) -> bool:
        return self.broker.protocol == "5"

    def _create_client(self) -> mqtt.Client:
        broker = self.broker
        client = mqtt.Client(
            callback_api_version=CallbackAPIVersion.VERSION2,
            client_id=broker.client_id,
            protocol=mqtt.MQTTv5 if self._is_v5 else mqtt.MQTTv311,
            transport=broker.transport,
            clean_session=None if self._is_v5 else broker.clean_start,
        )
        if broker.transport == "websockets":
            client.ws_set_options(path=broker.websocket_path, headers=broker.websocket_headers)
        if broker.tls is not None:
            client.tls_set_context(broker.tls.create_context())
            if broker.tls.insecure:
                client.tls_insecure_set(True)
        if broker.username is not None:
            client.username_pw_set(broker.username, broker.password)
        if broker.will is not None:
            will = broker.will
            client.will_set(will.topic, will.payload, qos=will.qos, retain=will.retain)
        client.reconnect_delay_set(broker.reconnect_min_delay, broker.reconnect_max_delay)
        return client

    def _publish_properties(self, message: Message) -> Properties | None:
        if not self._is_v5:
            return None
        properties = Properties(PacketTypes.PUBLISH)  # type: ignore[no-untyped-call]
        if message.response_topic:
            properties.ResponseTopic = message.response_topic
        if message.correlation_data is not None:
            properties.CorrelationData = message.correlation_data
        if message.content_type:
            properties.ContentType = message.content_type
        if message.user_properties:
            properties.UserProperty = list(message.user_properties)
        return None if properties.isEmpty() else properties  # type: ignore[no-untyped-call]


def _to_message(message: mqtt.MQTTMessage) -> Message:
    properties = getattr(message, "properties", None)
    return Message(
        topic=message.topic,
        payload=bytes(message.payload),
        qos=message.qos,
        retain=bool(message.retain),
        response_topic=getattr(properties, "ResponseTopic", None),
        correlation_data=getattr(properties, "CorrelationData", None),
        content_type=getattr(properties, "ContentType", None),
        user_properties=tuple(getattr(properties, "UserProperty", ())),
    )
