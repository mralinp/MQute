"""Topic patterns: MQTT filters with optional named parameters.

A pattern is an MQTT topic filter in which wildcard levels may be named::

    sensors/{device_id}/temperature   ->  sensors/+/temperature
    logs/{path:path}                  ->  logs/#
    sensors/+/humidity                ->  sensors/+/humidity   (anonymous)

Named single-level parameters (``{name}``) behave like ``+`` and named
multi-level parameters (``{name:path}``) behave like ``#``.
"""

from __future__ import annotations

import re
import string
from dataclasses import dataclass
from enum import Enum

from .exceptions import TopicError

_PARAM = re.compile(r"^\{(?P<name>[A-Za-z_][A-Za-z0-9_]*)(?P<path>:path)?\}$")
_SINGLE = "+"
_MULTI = "#"


class _Kind(Enum):
    LITERAL = "literal"
    SINGLE = "single"
    MULTI = "multi"


@dataclass(frozen=True)
class _Level:
    kind: _Kind
    value: str  # literal text, or the parameter name ("" when anonymous)

    @property
    def filter(self) -> str:
        if self.kind is _Kind.SINGLE:
            return _SINGLE
        if self.kind is _Kind.MULTI:
            return _MULTI
        return self.value


def join_topics(*parts: str) -> str:
    """Join topic fragments with exactly one ``/`` between non-empty parts."""
    cleaned = [part.strip("/") for part in parts if part.strip("/")]
    return "/".join(cleaned)


def validate_topic(topic: str) -> None:
    """Raise :class:`TopicError` unless ``topic`` is valid for publishing."""
    if not topic:
        raise TopicError("Topic must not be empty.")
    if _SINGLE in topic or _MULTI in topic:
        raise TopicError(f"Wildcards are not allowed in a publish topic: {topic!r}")


class TopicPattern:
    """A parsed topic pattern that can match concrete topics."""

    __slots__ = ("_levels", "filter", "params", "pattern")

    def __init__(self, pattern: str) -> None:
        if not pattern:
            raise TopicError("Topic pattern must not be empty.")
        if pattern.startswith("$share/"):
            raise TopicError("Use the share_group argument instead of a '$share/' prefix.")
        self.pattern = pattern
        self._levels = tuple(_parse_level(level, pattern) for level in pattern.split("/"))
        self._validate()
        self.filter = "/".join(level.filter for level in self._levels)
        self.params = tuple(level.value for level in self._levels if level.kind is not _Kind.LITERAL and level.value)

    def __repr__(self) -> str:
        return f"TopicPattern({self.pattern!r})"

    def match(self, topic: str) -> dict[str, str] | None:
        """Return the captured parameters if ``topic`` matches, otherwise ``None``."""
        levels = topic.split("/")
        # MQTT 4.7.2: wildcards at the first level never match '$' topics.
        if topic.startswith("$") and self._levels[0].kind is not _Kind.LITERAL:
            return None
        params: dict[str, str] = {}
        for index, level in enumerate(self._levels):
            if level.kind is _Kind.MULTI:
                if level.value:
                    params[level.value] = "/".join(levels[index:])
                return params
            if index >= len(levels):
                return None
            if level.kind is _Kind.LITERAL and level.value != levels[index]:
                return None
            if level.kind is _Kind.SINGLE and level.value:
                params[level.value] = levels[index]
        return params if len(levels) == len(self._levels) else None

    def _validate(self) -> None:
        names = [level.value for level in self._levels if level.kind is not _Kind.LITERAL and level.value]
        if len(names) != len(set(names)):
            raise TopicError(f"Duplicate parameter name in {self.pattern!r}")
        if any(level.kind is _Kind.MULTI for level in self._levels[:-1]):
            raise TopicError(f"A multi-level wildcard must be the last level: {self.pattern!r}")


def template_fields(template: str) -> set[str]:
    """Return the ``{field}`` names used in a response-topic template."""
    return {field for _, field, _, _ in string.Formatter().parse(template) if field}


def _parse_level(level: str, pattern: str) -> _Level:
    if level == _SINGLE:
        return _Level(_Kind.SINGLE, "")
    if level == _MULTI:
        return _Level(_Kind.MULTI, "")
    match = _PARAM.match(level)
    if match:
        kind = _Kind.MULTI if match["path"] else _Kind.SINGLE
        return _Level(kind, match["name"])
    if any(char in level for char in "+#{}"):
        raise TopicError(f"Invalid topic level {level!r} in {pattern!r}")
    return _Level(_Kind.LITERAL, level)
