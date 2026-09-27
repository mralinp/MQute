"""MQute: build MQTT applications the way you build web APIs with FastAPI."""

from importlib.metadata import PackageNotFoundError, version

from .app import MQute
from .broker import TLS, Broker, Will
from .dependencies import Depends
from .exceptions import MessageValidationError, MQuteError, PublishError, TopicError
from .message import Message
from .response import Response
from .routing import Router, Subscription
from .transport import PahoTransport, Transport, TransportEvents

try:
    __version__ = version("mqute")
except PackageNotFoundError:  # pragma: no cover - running from a source tree
    __version__ = "0.0.0"

__all__ = [
    "TLS",
    "Broker",
    "Depends",
    "MQute",
    "MQuteError",
    "Message",
    "MessageValidationError",
    "PahoTransport",
    "PublishError",
    "Response",
    "Router",
    "Subscription",
    "TopicError",
    "Transport",
    "TransportEvents",
    "Will",
    "__version__",
]
