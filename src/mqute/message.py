"""The immutable message model shared by incoming and outgoing MQTT traffic."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Message:
    """A single MQTT application message.

    The MQTT 5 properties (``response_topic``, ``correlation_data``,
    ``content_type`` and ``user_properties``) are empty when the broker
    speaks MQTT 3.1.1.
    """

    topic: str
    payload: bytes = b""
    qos: int = 0
    retain: bool = False
    response_topic: str | None = None
    correlation_data: bytes | None = None
    content_type: str | None = None
    user_properties: tuple[tuple[str, str], ...] = ()

    def text(self, encoding: str = "utf-8") -> str:
        """Return the payload decoded as text."""
        return self.payload.decode(encoding)

    def json(self) -> Any:
        """Return the payload parsed as JSON."""
        return json.loads(self.payload)
