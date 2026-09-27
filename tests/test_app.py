import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass, replace
from typing import Annotated

import pydantic
import pytest

from mqute import Depends, Message, MessageValidationError, MQute, Response, Router
from mqute.testing import MemoryTransport, TestClient


class Reading(pydantic.BaseModel):
    celsius: float


@dataclass
class Command:
    action: str


def test_topic_params_and_typed_payload(app: MQute):
    received = []

    @app.subscribe("sensors/{sensor_id}/temperature")
    async def temperature(sensor_id: int, reading: Reading) -> None:
        received.append((sensor_id, reading))

    with TestClient(app) as client:
        assert client.publish("sensors/7/temperature", {"celsius": 21.5}) == []

    assert received == [(7, Reading(celsius=21.5))]


def test_sync_handlers_run_off_the_event_loop(app: MQute):
    @app.subscribe("echo", response_topic="echo/reply")
    def echo(text: str) -> str:
        with pytest.raises(RuntimeError):
            asyncio.get_running_loop()
        return text.upper()

    with TestClient(app) as client:
        (reply,) = client.publish("echo", "hi")

    assert reply.topic == "echo/reply"
    assert reply.payload == b"HI"


def test_message_injection_and_response_topic_template(app: MQute):
    @app.subscribe("devices/{device_id}/command", response_topic="devices/{device_id}/ack", qos=1)
    async def command(device_id: str, cmd: Command, message: Message) -> dict[str, object]:
        return {"device": device_id, "action": cmd.action, "qos": message.qos}

    with TestClient(app) as client:
        (reply,) = client.publish("devices/d1/command", {"action": "reboot"}, qos=1)

    assert reply.topic == "devices/d1/ack"
    assert reply.json() == {"device": "d1", "action": "reboot", "qos": 1}


def test_mqtt5_request_response(app: MQute):
    @app.subscribe("rpc/add", response_topic="ignored/because/request/wins")
    async def add(numbers: list[int]) -> int:
        return sum(numbers)

    with TestClient(app) as client:
        (reply,) = client.publish("rpc/add", [1, 2, 3], response_topic="clients/42/inbox", correlation_data=b"req-1")

    assert (reply.topic, reply.payload, reply.correlation_data) == ("clients/42/inbox", b"6", b"req-1")


def test_explicit_response(app: MQute):
    @app.subscribe("status")
    async def status() -> Response:
        return Response({"ok": True}, topic="status/current", qos=1, retain=True, content_type="application/json")

    with TestClient(app) as client:
        (reply,) = client.publish("status")

    assert reply == Message("status/current", b'{"ok":true}', qos=1, retain=True, content_type="application/json")


def test_return_value_without_destination_is_dropped(app: MQute, caplog):
    @app.subscribe("fire-and-forget")
    async def handler() -> str:
        return "nobody listens"

    with TestClient(app) as client:
        assert client.publish("fire-and-forget") == []
    assert "no response topic" in caplog.text


def test_unrouted_messages_are_ignored(app: MQute):
    with TestClient(app) as client:
        assert client.publish("nothing/here", "x") == []


def test_dependencies(app: MQute):
    events = []

    async def get_session():
        events.append("open")
        yield "session"
        events.append("close")

    def get_device(device_id: str, session: Annotated[str, Depends(get_session)]) -> str:
        return f"{device_id}@{session}"

    @app.subscribe("devices/{device_id}", response_topic="out")
    async def handler(
        device: Annotated[str, Depends(get_device)],
        session: str = Depends(get_session),
    ) -> str:
        events.append("handler")
        return f"{device}|{session}"

    with TestClient(app) as client:
        (reply,) = client.publish("devices/d1")

    assert reply.text() == "d1@session|session"
    assert events == ["open", "handler", "close"]


def test_class_and_callable_dependencies(app: MQute):
    class Settings:
        def __init__(self, message: Message) -> None:
            self.topic = message.topic

    class Counter:
        def __init__(self) -> None:
            self.calls = 0

        async def __call__(self) -> int:
            self.calls += 1
            return self.calls

    counter = Counter()

    @app.subscribe("x", response_topic="out")
    def handler(
        settings: Settings = Depends(Settings),
        first: int = Depends(counter, use_cache=False),
        second: int = Depends(counter, use_cache=False),
    ) -> str:
        return f"{settings.topic}:{first}:{second}"

    with TestClient(app) as client:
        (reply,) = client.publish("x")

    assert reply.text() == "x:1:2"


def test_sync_generator_dependency(app: MQute):
    closed = []

    def resource():
        yield "r"
        closed.append(True)

    @app.subscribe("x")
    async def handler(value: str = Depends(resource)) -> None:
        assert value == "r"

    with TestClient(app) as client:
        client.publish("x")
    assert closed == [True]


def test_middleware_order_and_message_rewrite(app: MQute):
    calls = []
    router = Router(prefix="api")

    @app.middleware
    async def outer(message, call_next):
        calls.append("app")
        return await call_next(replace(message, payload=message.payload + b"!"))

    @router.middleware
    async def inner(message, call_next):
        calls.append("router")
        result = await call_next(message)
        return f"<{result}>"

    @router.subscribe("echo", response_topic="out")
    async def echo(text: str) -> str:
        calls.append("handler")
        return text

    app.include_router(router)

    with TestClient(app) as client:
        (reply,) = client.publish("api/echo", "hi")

    assert calls == ["app", "router", "handler"]
    assert reply.text() == "<hi!>"


def test_middleware_can_drop_messages(app: MQute):
    handled = []

    @app.middleware
    async def auth(message, call_next):
        if dict(message.user_properties).get("token") != "secret":
            return None
        return await call_next(message)

    @app.subscribe("secure")
    async def secure() -> None:
        handled.append(True)

    with TestClient(app) as client:
        client.publish("secure")
        client.publish("secure", user_properties=(("token", "secret"),))

    assert handled == [True]


def test_validation_errors_propagate_without_handler(app: MQute):
    @app.subscribe("temp")
    async def temp(reading: Reading) -> None: ...

    with TestClient(app) as client, pytest.raises(MessageValidationError):
        client.publish("temp", {"celsius": "hot"})


def test_exception_handlers(app: MQute):
    @app.exception_handler(MessageValidationError)
    async def invalid(message: Message, exc: Exception) -> Response:
        return Response({"error": str(exc)}, topic=f"{message.topic}/errors")

    @app.exception_handler(LookupError)
    def missing(message: Message, exc: Exception) -> None:
        return None

    @app.subscribe("temp")
    async def temp(reading: Reading) -> None: ...

    @app.subscribe("lookup")
    async def lookup() -> None:
        raise KeyError("x")

    with TestClient(app) as client:
        (reply,) = client.publish("temp", {"celsius": "hot"})
        assert client.publish("lookup") == []

    assert reply.topic == "temp/errors"
    assert "celsius" in reply.json()["error"]


def test_lifecycle_hooks_and_lifespan():
    events = []

    @asynccontextmanager
    async def lifespan(app):
        events.append("lifespan:start")
        yield
        events.append("lifespan:stop")

    transport = MemoryTransport()
    app = MQute(transport=transport, lifespan=lifespan)
    app.on_startup(lambda: events.append("startup"))
    app.on_shutdown(lambda: events.append("shutdown"))

    @app.on_connect
    async def connected():
        events.append("connect")

    @app.on_disconnect
    def disconnected(reason):
        events.append(f"disconnect:{reason}")

    @app.subscribe("a/{x}", qos=0)
    async def a(x: str) -> None: ...

    @app.subscribe("a/{y}", qos=2)
    async def b(y: str) -> None: ...

    with TestClient(app) as client:
        assert client.transport.subscriptions == [app.subscriptions()[0]]
        assert app.subscriptions()[0].qos == 2
        assert app.is_running

    assert not app.is_running
    assert events == [
        "lifespan:start",
        "startup",
        "connect",
        "disconnect:None",
        "shutdown",
        "lifespan:stop",
    ]
    assert app.transport is transport


def test_failed_startup_cleans_up():
    events = []
    app = MQute(transport=MemoryTransport())
    app.on_shutdown(lambda: events.append("shutdown"))

    @app.on_startup
    def boom():
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"), TestClient(app):
        pass
    assert events == ["shutdown"]
    assert not app.is_running


async def test_app_publish_and_double_start():
    transport = MemoryTransport()
    app = MQute(transport=transport)
    async with app:
        await app.publish("greetings", {"hello": "world"}, qos=1, retain=True)
        with pytest.raises(RuntimeError, match="already running"):
            await app.start()
    assert transport.published == [Message("greetings", b'{"hello":"world"}', qos=1, retain=True)]


async def test_messages_from_transport_are_processed_concurrently_and_drained():
    transport = MemoryTransport()
    app = MQute(transport=transport)
    done = []

    @app.subscribe("slow", response_topic="slow/done")
    async def slow(n: int) -> int:
        await asyncio.sleep(0.01)
        done.append(n)
        return n

    async with app:
        for n in range(3):
            app._on_message(Message("slow", str(n).encode()))
    assert sorted(done) == [0, 1, 2]
    assert len(transport.published) == 3


async def test_unhandled_errors_from_transport_are_logged(caplog):
    app = MQute(transport=MemoryTransport())

    @app.subscribe("boom")
    async def boom() -> None:
        raise ValueError("kaput")

    async with app:
        app._on_message(Message("boom"))
    assert "Unhandled error" in caplog.text


async def test_shutdown_timeout_cancels_stuck_handlers(caplog):
    app = MQute(transport=MemoryTransport(), shutdown_timeout=0.01)

    @app.subscribe("stuck")
    async def stuck() -> None:
        await asyncio.sleep(10)

    async with app:
        app._on_message(Message("stuck"))
        await asyncio.sleep(0)
    assert "Cancelled 1" in caplog.text


async def test_serve_stops_on_cancel():
    app = MQute(transport=MemoryTransport())
    task = asyncio.create_task(app.serve())
    await asyncio.sleep(0.01)
    assert app.is_running
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not app.is_running


def test_broker_url_from_environment(monkeypatch):
    monkeypatch.setenv("MQUTE_BROKER_URL", "mqtts://env-host")
    app = MQute()
    assert app.broker.host == "env-host"
    assert app.broker.tls is not None


def test_test_client_requires_context_manager(app: MQute):
    with pytest.raises(RuntimeError, match="context manager"):
        TestClient(app).publish("x")
