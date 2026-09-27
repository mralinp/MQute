"""Round trips through a real broker. Run with e.g.

mosquitto -p 1883 &
MQUTE_TEST_BROKER_URL=mqtt://localhost:1883 pytest -m integration
"""

import asyncio
import os
import uuid

import pytest

from mqute import Broker, Message, MQute

BROKER_URL = os.environ.get("MQUTE_TEST_BROKER_URL")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not BROKER_URL, reason="set MQUTE_TEST_BROKER_URL to run against a real broker"),
]


def _broker(protocol: str) -> Broker:
    assert BROKER_URL is not None
    return Broker.from_url(BROKER_URL, protocol=protocol)


@pytest.mark.parametrize("protocol", ["5", "3.1.1"])
async def test_round_trip(protocol: str) -> None:
    base = f"mqute-test/{uuid.uuid4().hex}"
    service = MQute(_broker(protocol))
    caller = MQute(_broker(protocol))
    replies: asyncio.Queue[Message] = asyncio.Queue()

    @service.subscribe(base + "/devices/{device_id}/ping", response_topic=base + "/devices/{device_id}/pong", qos=1)
    async def ping(device_id: str, payload: dict[str, int]) -> dict[str, object]:
        return {"device": device_id, "n": payload["n"] + 1}

    @caller.subscribe(base + "/devices/+/pong", qos=1)
    async def pong(message: Message) -> None:
        await replies.put(message)

    async with service, caller:
        await caller.publish(base + "/devices/d1/ping", {"n": 1}, qos=1)
        reply = await asyncio.wait_for(replies.get(), timeout=5)

    assert reply.topic == base + "/devices/d1/pong"
    assert reply.json() == {"device": "d1", "n": 2}


async def test_mqtt5_response_topic_and_correlation_data() -> None:
    base = f"mqute-test/{uuid.uuid4().hex}"
    service = MQute(_broker("5"))
    caller = MQute(_broker("5"))
    replies: asyncio.Queue[Message] = asyncio.Queue()

    @service.subscribe(base + "/rpc/sum")
    async def add(numbers: list[int]) -> int:
        return sum(numbers)

    @caller.subscribe(base + "/inbox")
    async def inbox(message: Message) -> None:
        await replies.put(message)

    async with service, caller:
        await caller.publish(base + "/rpc/sum", [1, 2, 3], response_topic=base + "/inbox", correlation_data=b"42")
        reply = await asyncio.wait_for(replies.get(), timeout=5)

    assert (reply.payload, reply.correlation_data) == (b"6", b"42")


async def test_connects_with_credentials() -> None:
    app = MQute(_broker("5").with_options(username="anyone", password="x"))
    async with app:
        assert app.is_running
