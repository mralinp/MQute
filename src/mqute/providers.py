"""Ready-made :class:`~mqute.Broker` settings for popular hosted brokers.

These are conveniences only: every provider can also be configured with
``Broker(...)`` or ``Broker.from_url(...)``. Keyword arguments are passed on
to :class:`~mqute.Broker`, so any setting can still be overridden.
"""

from __future__ import annotations

from typing import Any

from .broker import TLS, Broker


def mosquitto(host: str = "localhost", port: int = 1883, **options: Any) -> Broker:
    """A self-hosted broker (Mosquitto, NanoMQ, VerneMQ, ...) without TLS."""
    return Broker(host=host, port=port, **options)


def hivemq_cloud(host: str, username: str, password: str, *, websockets: bool = False, **options: Any) -> Broker:
    """HiveMQ Cloud cluster: TLS on 8883, or secure WebSockets on 8884."""
    if websockets:
        return Broker(
            host=host,
            port=8884,
            transport="websockets",
            tls=TLS(),
            username=username,
            password=password,
            **options,
        )
    return Broker(host=host, port=8883, tls=TLS(), username=username, password=password, **options)


def hivemq_public(**options: Any) -> Broker:
    """HiveMQ's public test broker. Never send private data to it."""
    return Broker(host="broker.hivemq.com", port=1883, **options)


def emqx_cloud(host: str, username: str, password: str, *, websockets: bool = False, **options: Any) -> Broker:
    """EMQX Cloud / Serverless deployment: TLS on 8883, or secure WebSockets on 8084."""
    if websockets:
        return Broker(
            host=host,
            port=8084,
            transport="websockets",
            tls=TLS(),
            username=username,
            password=password,
            **options,
        )
    return Broker(host=host, port=8883, tls=TLS(), username=username, password=password, **options)


def aws_iot(
    endpoint: str,
    *,
    client_id: str,
    certfile: str,
    keyfile: str,
    ca_certs: str | None = None,
    port: int = 8883,
    **options: Any,
) -> Broker:
    """AWS IoT Core with X.509 client certificates.

    Port 443 is supported through ALPN (``x-amzn-mqtt-ca``) for networks that
    only allow HTTPS traffic.
    """
    alpn = ("x-amzn-mqtt-ca",) if port == 443 else ()
    tls = TLS(ca_certs=ca_certs, certfile=certfile, keyfile=keyfile, alpn_protocols=alpn)
    return Broker(host=endpoint, port=port, tls=tls, client_id=client_id, **options)
