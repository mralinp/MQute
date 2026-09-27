import socket

import paho.mqtt.client as mqtt
import pytest
from paho.mqtt.packettypes import PacketTypes
from paho.mqtt.properties import Properties

from mqute import TLS, Broker, Message, PahoTransport, PublishError, TransportEvents, Will
from mqute.transport import _to_message


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _events() -> TransportEvents:
    return TransportEvents(on_message=lambda m: None, on_connect=lambda: None, on_disconnect=lambda r: None)


def test_client_configuration_v5_websockets_tls():
    broker = Broker(
        host="h",
        transport="websockets",
        tls=TLS(insecure=True),
        username="u",
        password="p",
        client_id="cid",
        websocket_path="/ws",
        will=Will("status", "offline", qos=1, retain=True),
    )
    client = PahoTransport(broker)._create_client()
    assert client.protocol == mqtt.MQTTv5
    assert client.transport == "websockets"
    assert client.username == "u"
    assert client._client_id == b"cid"


def test_client_configuration_v311():
    client = PahoTransport(Broker(protocol="3.1.1", clean_start=False))._create_client()
    assert client.protocol == mqtt.MQTTv311
    assert client._clean_session is False


def test_publish_properties_only_for_v5():
    message = Message(
        "t",
        response_topic="r",
        correlation_data=b"c",
        content_type="text/plain",
        user_properties=(("k", "v"),),
    )
    properties = PahoTransport(Broker())._publish_properties(message)
    assert properties is not None
    assert properties.ResponseTopic == "r"
    assert properties.CorrelationData == b"c"
    assert properties.UserProperty == [("k", "v")]
    assert PahoTransport(Broker())._publish_properties(Message("t")) is None
    assert PahoTransport(Broker(protocol="3.1.1"))._publish_properties(message) is None


def test_incoming_message_conversion():
    raw = mqtt.MQTTMessage(topic=b"a/b")
    raw.payload = b"data"
    raw.qos = 1
    raw.retain = True
    raw.properties = Properties(PacketTypes.PUBLISH)
    raw.properties.ResponseTopic = "reply"
    raw.properties.CorrelationData = b"id"
    raw.properties.UserProperty = ("k", "v")
    assert _to_message(raw) == Message(
        "a/b",
        b"data",
        qos=1,
        retain=True,
        response_topic="reply",
        correlation_data=b"id",
        user_properties=(("k", "v"),),
    )


async def test_connect_to_unreachable_broker_fails_fast():
    transport = PahoTransport(Broker(port=_free_port(), connect_timeout=5))
    with pytest.raises(ConnectionError):
        await transport.connect([], _events())
    assert transport.client is None


async def test_publish_requires_connection():
    with pytest.raises(PublishError):
        await PahoTransport(Broker()).publish(Message("t"))
    await PahoTransport(Broker()).disconnect()  # no-op when not connected
