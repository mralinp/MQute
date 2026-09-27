from dataclasses import dataclass
from typing import Annotated, Any

import pydantic
import pytest

from mqute.encoding import convert_text, decode, encode
from mqute.exceptions import MessageValidationError


@dataclass
class Point:
    x: int
    y: int


class Reading(pydantic.BaseModel):
    celsius: float


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, b""),
        (b"raw", b"raw"),
        (bytearray(b"raw"), b"raw"),
        ("text", b"text"),
        ({"a": 1}, b'{"a":1}'),
        ([1, 2], b"[1,2]"),
        (42, b"42"),
        (True, b"true"),
        (Point(1, 2), b'{"x":1,"y":2}'),
        (Reading(celsius=21.5), b'{"celsius":21.5}'),
    ],
)
def test_encode(value, expected):
    assert encode(value) == expected


def test_encode_rejects_unserialisable_values():
    with pytest.raises(TypeError):
        encode(object())


@pytest.mark.parametrize(
    ("payload", "annotation", "expected"),
    [
        (b"raw", bytes, b"raw"),
        (b"hello", str, "hello"),
        (b"42", int, 42),
        (b" 2.5 ", float, 2.5),
        (b"true", bool, True),
        (b"off", bool, False),
        (b'{"a": 1}', dict, {"a": 1}),
        (b'{"a": 1}', dict[str, int], {"a": 1}),
        (b"[1, 2]", list, [1, 2]),
        (b'{"x": 1, "y": 2}', Point, Point(1, 2)),
        (b'{"celsius": 3}', Reading, Reading(celsius=3)),
        (b"", Reading | None, None),
        (b'{"celsius": 3}', Reading | None, Reading(celsius=3)),
        (b"7", Annotated[int, "meta"], 7),
    ],
)
def test_decode_by_annotation(payload, annotation, expected):
    assert decode(payload, annotation) == expected


@pytest.mark.parametrize(
    ("payload", "expected"),
    [(b'{"a": 1}', {"a": 1}), (b"plain text", "plain text"), (b"\xff\xfe", b"\xff\xfe"), (b"3", 3)],
)
def test_decode_without_annotation_guesses(payload, expected):
    assert decode(payload, Any) == expected


@pytest.mark.parametrize(
    ("payload", "annotation"),
    [
        (b"abc", int),
        (b"maybe", bool),
        (b"[1]", dict),
        (b"not json", dict),
        (b'{"celsius": "hot"}', Reading),
        (b'{"x": 1}', Point),
    ],
)
def test_decode_errors_become_validation_errors(payload, annotation):
    with pytest.raises(MessageValidationError):
        decode(payload, annotation)


def test_convert_text():
    assert convert_text("5", int) == 5
    assert convert_text("yes", bool) is True
    assert convert_text("x", str) == "x"
    with pytest.raises(MessageValidationError):
        convert_text("x", int)
