import pytest

from mqute import Router, Subscription, TopicError


def handler(payload):
    return payload


def test_subscribe_registers_route_with_prefix():
    router = Router(prefix="devices")
    router.subscribe("{device_id}/status", qos=1)(handler)
    (route,) = router.routes
    assert route.pattern.pattern == "devices/{device_id}/status"
    assert route.subscription == Subscription("devices/+/status", 1)


def test_share_group_subscription():
    router = Router()
    route = router.add_route("jobs/{job_id}", handler, share_group="workers")
    assert route.subscription.topic == "$share/workers/jobs/+"


def test_include_router_nests_prefixes():
    floor = Router(prefix="floor1")
    floor.subscribe("room/{room}")(handler)
    building = Router(prefix="building1")
    building.include_router(floor, prefix="floors")
    root = Router()
    root.include_router(building, prefix="buildings")

    matched = root.match("buildings/building1/floors/floor1/room/42")
    assert matched is not None
    assert matched[1] == {"room": "42"}


def test_first_matching_route_wins():
    router = Router()
    router.add_route("a/special", handler)
    router.add_route("a/{name}", handler)
    matched = router.match("a/special")
    assert matched is not None
    assert matched[0].pattern.pattern == "a/special"
    assert router.match("b") is None


def test_invalid_qos_is_rejected():
    with pytest.raises(ValueError, match="QoS"):
        Router().add_route("a", handler, qos=3)


def test_response_topic_must_use_known_params():
    with pytest.raises(TopicError, match="unknown"):
        Router().add_route("a/{x}", handler, response_topic="b/{y}")


def test_middleware_must_be_async():
    with pytest.raises(TypeError, match="async"):
        Router().middleware(lambda message, call_next: None)


def test_handler_signature_is_checked_at_registration():
    def two_payloads(first, second):
        return None

    with pytest.raises(TypeError, match="only one payload"):
        Router().add_route("a", two_payloads)

    def var_args(*args):
        return None

    with pytest.raises(TypeError, match="regular or keyword"):
        Router().add_route("a", var_args)
