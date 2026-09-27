"""Conversion between Python values and MQTT payload bytes.

Decoding is driven by type annotations; encoding by the runtime type of the
value. Pydantic models are supported through duck typing, so pydantic is never
imported by MQute itself.
"""

from __future__ import annotations

import dataclasses
import inspect
import json
import types
import typing
from typing import Any

from .exceptions import MessageValidationError

_MISSING = inspect.Parameter.empty
_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


def encode(value: Any) -> bytes:
    """Serialize a handler result into payload bytes."""
    if value is None:
        return b""
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value)
    if isinstance(value, str):
        return value.encode()
    if hasattr(value, "model_dump_json"):  # pydantic v2
        return str(value.model_dump_json()).encode()
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        value = dataclasses.asdict(value)
    return json.dumps(value, separators=(",", ":")).encode()


def decode(payload: bytes, annotation: Any) -> Any:
    """Convert payload bytes into an instance of ``annotation``."""
    try:
        return _decode(payload, annotation)
    except MessageValidationError:
        raise
    except Exception as exc:
        raise MessageValidationError(f"Payload cannot be converted to {_name(annotation)}: {exc}") from exc


def convert_text(value: str, annotation: Any) -> Any:
    """Convert a topic parameter (always text) to ``annotation``."""
    if annotation in (Any, str, _MISSING):
        return value
    if annotation is bool:
        return _parse_bool(value)
    try:
        return annotation(value)
    except Exception as exc:
        raise MessageValidationError(f"Topic value {value!r} is not a valid {_name(annotation)}") from exc


def _decode(payload: bytes, annotation: Any) -> Any:
    annotation = _strip_annotated(annotation)
    inner = _optional_inner(annotation)
    if inner is not None:
        return None if not payload else _decode(payload, inner)
    if annotation in (_MISSING, Any, object):
        return _decode_auto(payload)
    if annotation in (bytes, bytearray, memoryview):
        return annotation(payload)
    if annotation is str:
        return payload.decode()
    if annotation is bool:
        return _parse_bool(payload.decode().strip())
    if annotation in (int, float):
        return annotation(payload.decode().strip())
    if hasattr(annotation, "model_validate_json"):  # pydantic v2
        return annotation.model_validate_json(payload)
    if dataclasses.is_dataclass(annotation) and isinstance(annotation, type):
        return annotation(**json.loads(payload))
    return _decode_json(payload, annotation)


def _decode_auto(payload: bytes) -> Any:
    """Best effort for unannotated payloads: JSON, then text, then raw bytes."""
    try:
        text = payload.decode()
    except UnicodeDecodeError:
        return payload
    try:
        return json.loads(text)
    except ValueError:
        return text


def _decode_json(payload: bytes, annotation: Any) -> Any:
    value = json.loads(payload)
    expected = typing.get_origin(annotation) or annotation
    if isinstance(expected, type) and not isinstance(value, expected):
        raise MessageValidationError(f"Expected {_name(annotation)}, got {type(value).__name__}")
    return value


def _parse_bool(text: str) -> bool:
    lowered = text.lower()
    if lowered in _TRUE:
        return True
    if lowered in _FALSE:
        return False
    raise MessageValidationError(f"{text!r} is not a valid boolean")


def _strip_annotated(annotation: Any) -> Any:
    if typing.get_origin(annotation) is typing.Annotated:
        return typing.get_args(annotation)[0]
    return annotation


def _optional_inner(annotation: Any) -> Any:
    """Return ``X`` for ``X | None``; ``None`` for anything else."""
    if typing.get_origin(annotation) not in (typing.Union, types.UnionType):
        return None
    args = [arg for arg in typing.get_args(annotation) if arg is not type(None)]
    if len(args) == 1 and len(typing.get_args(annotation)) == 2:
        return args[0]
    return None


def _name(annotation: Any) -> str:
    return getattr(annotation, "__name__", None) or repr(annotation)
