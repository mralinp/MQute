import pytest

from mqute.exceptions import TopicError
from mqute.topics import TopicPattern, join_topics, template_fields, validate_topic


@pytest.mark.parametrize(
    ("pattern", "expected_filter", "expected_params"),
    [
        ("sensors/temperature", "sensors/temperature", ()),
        ("sensors/{sensor_id}/temperature", "sensors/+/temperature", ("sensor_id",)),
        ("logs/{rest:path}", "logs/#", ("rest",)),
        ("a/+/b/#", "a/+/b/#", ()),
        ("{site}/{device}", "+/+", ("site", "device")),
    ],
)
def test_pattern_builds_mqtt_filter(pattern, expected_filter, expected_params):
    parsed = TopicPattern(pattern)
    assert parsed.filter == expected_filter
    assert parsed.params == expected_params


@pytest.mark.parametrize(
    ("pattern", "topic", "expected"),
    [
        ("a/b", "a/b", {}),
        ("a/b", "a/c", None),
        ("a/b", "a/b/c", None),
        ("a/{x}", "a/1", {"x": "1"}),
        ("a/{x}", "a", None),
        ("a/{x}", "a/", {"x": ""}),
        ("a/+", "a/1", {}),
        ("a/{rest:path}", "a/1/2/3", {"rest": "1/2/3"}),
        ("a/{rest:path}", "a", {"rest": ""}),
        ("a/#", "a/b", {}),
        ("#", "anything/at/all", {}),
        ("#", "$SYS/broker/uptime", None),
        ("+/uptime", "$SYS/uptime", None),
        ("$SYS/{metric}", "$SYS/uptime", {"metric": "uptime"}),
    ],
)
def test_pattern_matching(pattern, topic, expected):
    assert TopicPattern(pattern).match(topic) == expected


@pytest.mark.parametrize(
    "pattern",
    ["", "a/#/b", "a/{x}/{x}", "a/b+", "a/{1x}", "a/{x:int}", "$share/group/a", "a/{rest:path}/b"],
)
def test_invalid_patterns_are_rejected(pattern):
    with pytest.raises(TopicError):
        TopicPattern(pattern)


def test_join_topics_normalises_slashes():
    assert join_topics("devices/", "/status") == "devices/status"
    assert join_topics("", "status") == "status"
    assert join_topics("a", "", "b") == "a/b"


def test_validate_topic():
    validate_topic("a/b")
    for bad in ("", "a/+", "a/#"):
        with pytest.raises(TopicError):
            validate_topic(bad)


def test_template_fields():
    assert template_fields("devices/{device_id}/ack") == {"device_id"}
    assert template_fields("static") == set()


def test_repr():
    assert repr(TopicPattern("a/b")) == "TopicPattern('a/b')"
