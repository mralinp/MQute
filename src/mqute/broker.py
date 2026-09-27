"""Broker connection settings, independent of any MQTT client library."""

from __future__ import annotations

import secrets
import ssl
from dataclasses import dataclass, field, replace
from typing import Any, Literal
from urllib.parse import parse_qs, unquote, urlsplit

TransportName = Literal["tcp", "websockets"]
ProtocolVersion = Literal["3.1.1", "5"]

_SCHEMES: dict[str, tuple[TransportName, bool]] = {
    "mqtt": ("tcp", False),
    "tcp": ("tcp", False),
    "mqtts": ("tcp", True),
    "ssl": ("tcp", True),
    "tls": ("tcp", True),
    "ws": ("websockets", False),
    "wss": ("websockets", True),
}
_DEFAULT_PORTS = {("tcp", False): 1883, ("tcp", True): 8883, ("websockets", False): 80, ("websockets", True): 443}


@dataclass(frozen=True)
class TLS:
    """TLS settings. ``TLS()`` verifies the server against the system CA store."""

    ca_certs: str | None = None
    certfile: str | None = None
    keyfile: str | None = None
    keyfile_password: str | None = field(default=None, repr=False)
    alpn_protocols: tuple[str, ...] = ()
    insecure: bool = False

    def create_context(self) -> ssl.SSLContext:
        context = ssl.create_default_context(cafile=self.ca_certs)
        if self.certfile:
            context.load_cert_chain(self.certfile, self.keyfile, self.keyfile_password)
        if self.alpn_protocols:
            context.set_alpn_protocols(list(self.alpn_protocols))
        if self.insecure:
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
        return context


@dataclass(frozen=True)
class Will:
    """Last-will message the broker publishes if the client disappears."""

    topic: str
    payload: bytes | str = b""
    qos: int = 0
    retain: bool = False


def _generate_client_id() -> str:
    return f"mqute-{secrets.token_hex(4)}"


@dataclass(frozen=True)
class Broker:
    """Where and how to connect.

    Works with any MQTT 3.1.1 or 5 broker: Mosquitto, EMQX, HiveMQ,
    VerneMQ, RabbitMQ, NanoMQ, AWS IoT Core, ... Build it directly or from
    a URL with :meth:`from_url`.
    """

    host: str = "localhost"
    port: int | None = None
    transport: TransportName = "tcp"
    tls: TLS | None = None
    username: str | None = None
    password: str | None = field(default=None, repr=False)
    client_id: str = field(default_factory=_generate_client_id)
    protocol: ProtocolVersion = "5"
    keepalive: int = 60
    clean_start: bool = True
    websocket_path: str = "/mqtt"
    websocket_headers: dict[str, str] | None = None
    will: Will | None = None
    connect_timeout: float = 10.0
    reconnect_min_delay: int = 1
    reconnect_max_delay: int = 60

    @property
    def resolved_port(self) -> int:
        """The explicit port, or the conventional one for the transport and TLS setting."""
        if self.port is not None:
            return self.port
        return _DEFAULT_PORTS[(self.transport, self.tls is not None)]

    @classmethod
    def from_url(cls, url: str, **overrides: Any) -> Broker:
        """Build settings from a URL such as ``mqtts://user:pass@host:8883``.

        Supported schemes: ``mqtt``/``tcp``, ``mqtts``/``ssl``/``tls``, ``ws``
        and ``wss``. The path is used as the WebSocket path, and the
        ``client_id`` query parameter is honoured. Keyword arguments override
        anything parsed from the URL.
        """
        parts = urlsplit(url)
        scheme = parts.scheme.lower()
        if scheme not in _SCHEMES:
            raise ValueError(f"Unsupported broker URL scheme {parts.scheme!r}; use one of {sorted(_SCHEMES)}")
        transport, secure = _SCHEMES[scheme]
        settings: dict[str, Any] = {
            "host": parts.hostname or "localhost",
            "port": parts.port,
            "transport": transport,
            "tls": TLS() if secure else None,
            "username": unquote(parts.username) if parts.username else None,
            "password": unquote(parts.password) if parts.password else None,
        }
        if transport == "websockets" and parts.path:
            settings["websocket_path"] = parts.path
        client_id = parse_qs(parts.query).get("client_id")
        if client_id:
            settings["client_id"] = client_id[0]
        settings.update(overrides)
        return cls(**settings)

    def with_options(self, **changes: Any) -> Broker:
        """Return a copy with some settings changed."""
        return replace(self, **changes)
