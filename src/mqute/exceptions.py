"""Exceptions raised by MQute."""

from __future__ import annotations


class MQuteError(Exception):
    """Base class for every error raised by MQute."""


class TopicError(MQuteError, ValueError):
    """A topic or topic pattern is not valid."""


class MessageValidationError(MQuteError):
    """An incoming message could not be converted into the handler's parameters."""


class PublishError(MQuteError):
    """A message could not be handed over to the broker."""
