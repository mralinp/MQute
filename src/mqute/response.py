"""Explicit replies returned from handlers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Response:
    """Full control over the reply a handler publishes.

    Returning a plain value from a handler is equivalent to returning
    ``Response(value)``. Use ``Response`` when you need to pick the topic,
    QoS, retain flag or MQTT 5 properties of the reply.
    """

    payload: Any = None
    topic: str | None = None
    qos: int = 0
    retain: bool = False
    content_type: str | None = None
    user_properties: tuple[tuple[str, str], ...] = ()
