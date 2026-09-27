import ssl

import pytest

from mqute import TLS, Broker, providers


def test_defaults():
    broker = Broker()
    assert broker.host == "localhost"
    assert broker.resolved_port == 1883
    assert broker.protocol == "5"
    assert broker.client_id.startswith("mqute-")
    assert Broker().client_id != broker.client_id


@pytest.mark.parametrize(
    ("url", "transport", "secure", "port"),
    [
        ("mqtt://example.com", "tcp", False, 1883),
        ("tcp://example.com:1884", "tcp", False, 1884),
        ("mqtts://example.com", "tcp", True, 8883),
        ("ws://example.com", "websockets", False, 80),
        ("wss://example.com:8884/mqtt", "websockets", True, 8884),
    ],
)
def test_from_url(url, transport, secure, port):
    broker = Broker.from_url(url)
    assert broker.host == "example.com"
    assert broker.transport == transport
    assert (broker.tls is not None) is secure
    assert broker.resolved_port == port


def test_from_url_credentials_path_and_client_id():
    broker = Broker.from_url("wss://us%40r:p%3Ass@host/ws?client_id=abc")
    assert broker.username == "us@r"
    assert broker.password == "p:ss"
    assert broker.websocket_path == "/ws"
    assert broker.client_id == "abc"


def test_from_url_overrides_and_with_options():
    broker = Broker.from_url("mqtt://host", protocol="3.1.1")
    assert broker.protocol == "3.1.1"
    assert broker.with_options(port=2000).resolved_port == 2000


def test_from_url_rejects_unknown_scheme():
    with pytest.raises(ValueError, match="scheme"):
        Broker.from_url("http://host")


def test_password_is_not_in_repr():
    assert "secret" not in repr(Broker(username="u", password="secret"))


def test_tls_context():
    context = TLS(alpn_protocols=("x-amzn-mqtt-ca",)).create_context()
    assert context.verify_mode == ssl.CERT_REQUIRED
    insecure = TLS(insecure=True).create_context()
    assert insecure.verify_mode == ssl.CERT_NONE
    assert not insecure.check_hostname


def test_providers():
    hive = providers.hivemq_cloud("abc.s1.eu.hivemq.cloud", "user", "pw")
    assert (hive.resolved_port, hive.tls is not None) == (8883, True)
    hive_ws = providers.hivemq_cloud("abc.s1.eu.hivemq.cloud", "user", "pw", websockets=True)
    assert (hive_ws.transport, hive_ws.resolved_port) == ("websockets", 8884)
    assert providers.hivemq_public().host == "broker.hivemq.com"
    emqx = providers.emqx_cloud("x.emqxsl.com", "u", "p", websockets=True)
    assert (emqx.resolved_port, emqx.websocket_path) == (8084, "/mqtt")
    assert providers.emqx_cloud("x.emqxsl.com", "u", "p").resolved_port == 8883
    assert providers.mosquitto(client_id="me").client_id == "me"
    aws = providers.aws_iot("id.iot.eu-west-1.amazonaws.com", client_id="thing", certfile="c", keyfile="k", port=443)
    assert aws.tls is not None
    assert aws.tls.alpn_protocols == ("x-amzn-mqtt-ca",)
