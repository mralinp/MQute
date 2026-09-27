<p align="center">
  <img src="https://raw.githubusercontent.com/mralinp/mqute/main/assets/cute-modern.png" width="40%" alt="MQute logo" />
</p>

<h1 align="center">MQute</h1>

<p align="center">
  <b>Build MQTT applications the way you build web APIs with FastAPI.</b>
</p>

<p align="center">
  <a href="https://github.com/mralinp/mqute/actions/workflows/ci.yml"><img src="https://github.com/mralinp/mqute/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://pypi.org/project/mqute/"><img src="https://img.shields.io/pypi/v/mqute.svg" alt="PyPI"></a>
  <a href="https://pypi.org/project/mqute/"><img src="https://img.shields.io/pypi/pyversions/mqute.svg" alt="Python versions"></a>
  <a href="LICENSE"><img src="https://img.shields.io/pypi/l/mqute.svg" alt="License"></a>
</p>

---

MQute (*MQ(TT) + cute*) is a small, typed, async-first framework for MQTT services.
Decorate a function with a topic, declare the parameters you want, and MQute
subscribes, parses, validates, calls your code and publishes the reply.

```python
from mqute import MQute

app = MQute("mqtt://localhost:1883")

@app.subscribe("sensors/{room}/temperature", response_topic="sensors/{room}/fahrenheit")
async def temperature(room: str, celsius: float) -> dict:
    return {"room": room, "fahrenheit": celsius * 9 / 5 + 32}
```

```bash
mqute run main:app
```

## Highlights

- **FastAPI ergonomics**: decorators, routers with prefixes, dependency injection with `Depends`, middleware, lifespan, exception handlers and a `TestClient`.
- **Typed topics and payloads**: `{param}` topic segments become typed arguments; payloads are decoded from your annotation (`bytes`, `str`, `int`, `dict`, dataclasses or Pydantic models).
- **Works with any broker**: Mosquitto, EMQX, HiveMQ, VerneMQ, NanoMQ, RabbitMQ, AWS IoT Core and more, over TCP, TLS, mutual TLS or WebSockets, on MQTT 5 or 3.1.1.
- **MQTT 5 native**: request/response via `response_topic` and `correlation_data`, user properties, content types and shared subscriptions.
- **Minimal**: one runtime dependency (`paho-mqtt`). Pydantic is optional.
- **Production minded**: automatic reconnects and resubscription, graceful shutdown that drains in-flight messages, SIGTERM handling, fully typed (`py.typed`, `mypy --strict`).

## Installation

```bash
pip install mqute               # core
pip install "mqute[pydantic]"   # add Pydantic model support
```

Requires Python 3.10+.

## Guide

### Connecting to a broker

Pass a URL, a `Broker`, or nothing at all to read `MQUTE_BROKER_URL` (default `mqtt://localhost`).

```python
from mqute import MQute, Broker, TLS

MQute("mqtt://localhost:1883")                         # plain TCP
MQute("mqtts://user:secret@broker.example.com")        # TLS, port 8883
MQute("wss://broker.example.com:8084/mqtt")            # secure WebSockets
MQute(Broker(                                          # everything explicit
    host="broker.example.com",
    port=8883,
    tls=TLS(ca_certs="ca.pem", certfile="client.crt", keyfile="client.key"),
    client_id="orders-service",
    protocol="3.1.1",
))
```

Ready-made settings for popular hosted brokers live in `mqute.providers`:

```python
from mqute import MQute, providers

MQute(providers.hivemq_cloud("xxxx.s1.eu.hivemq.cloud", "user", "password"))
MQute(providers.emqx_cloud("xxxx.emqxsl.com", "user", "password", websockets=True))
MQute(providers.aws_iot("xxxx-ats.iot.eu-west-1.amazonaws.com",
                        client_id="thing-1", certfile="cert.pem", keyfile="key.pem"))
MQute(providers.mosquitto("localhost"))
```

| `Broker` option | Default | Notes |
| --- | --- | --- |
| `host`, `port` | `localhost`, by transport | 1883 / 8883 (TLS) / 80 (ws) / 443 (wss) |
| `transport` | `"tcp"` | or `"websockets"` (+ `websocket_path`, `websocket_headers`) |
| `tls` | `None` | `TLS()` uses the system CA store; supports client certs, ALPN, `insecure` |
| `username`, `password` | `None` | |
| `client_id` | random `mqute-xxxxxxxx` | set it for persistent sessions |
| `protocol` | `"5"` | or `"3.1.1"` |
| `keepalive`, `clean_start` | `60`, `True` | |
| `will` | `None` | `Will(topic, payload, qos, retain)` |
| `connect_timeout` | `10.0` | startup fails if the first connection takes longer |
| `reconnect_min_delay`, `reconnect_max_delay` | `1`, `60` | reconnects are automatic |

Anything not covered (Azure IoT Hub SAS tokens, custom sockets, other client libraries)
can be plugged in by implementing the small `mqute.Transport` interface.

### Topics and parameters

Topic patterns are MQTT filters where wildcards can have names:

| Pattern | Subscribes to | Handler receives |
| --- | --- | --- |
| `sensors/{sensor_id}/temp` | `sensors/+/temp` | `sensor_id` |
| `logs/{path:path}` | `logs/#` | `path` (the remaining levels, e.g. `"a/b/c"`) |
| `sensors/+/temp` | `sensors/+/temp` | nothing extra |

Handler parameters are resolved like this:

1. Named like a topic parameter → the topic value, converted to its annotation (`str`, `int`, `float`, `bool`).
2. Annotated as `Message` → the raw message (topic, payload, QoS, retain, MQTT 5 properties).
3. Declared with `Depends(...)` → the dependency's result.
4. Any other parameter (at most one) → the payload, decoded from its annotation:

| Annotation | Decoded as |
| --- | --- |
| `bytes` | raw payload |
| `str` | UTF-8 text |
| `int`, `float`, `bool` | parsed text |
| `dict`, `list`, `dict[str, int]`, ... | JSON |
| dataclass | JSON object → `Cls(**data)` |
| Pydantic model | `Model.model_validate_json(payload)` |
| `X \| None` | `None` for an empty payload |
| none / `Any` | JSON if possible, else text, else bytes |

Signatures are checked when the route is registered, so mistakes fail at import time and not at 3 a.m.

Routes are matched in registration order; the first match handles the message. Each message
runs in its own task, so handlers run concurrently. Sync handlers run in a worker thread so they
never block the event loop.

### Replies

A handler's non-`None` return value is published as the reply:

- to the incoming message's MQTT 5 `response_topic` (with its `correlation_data`), otherwise
- to the route's `response_topic`, which can use topic parameters.

Return a `Response` for full control:

```python
from mqute import Response

@app.subscribe("devices/{device_id}/status")
async def status(device_id: str) -> Response:
    return Response({"online": True}, topic=f"devices/{device_id}/state", qos=1, retain=True)
```

Values are encoded as-is for `bytes`/`str`, and as JSON for everything else (dataclasses and
Pydantic models included). Publish from anywhere with `await app.publish(topic, payload, qos=1)`.

### Routers

```python
from mqute import Router

devices = Router(prefix="devices")

@devices.subscribe("{device_id}/command", qos=1, response_topic="devices/{device_id}/ack")
async def command(device_id: str, cmd: Command) -> dict:
    ...

app.include_router(devices)                     # devices/{device_id}/command
app.include_router(devices, prefix="site-a")    # site-a/devices/{device_id}/command
```

Use `share_group="workers"` on a route to create an MQTT 5 shared subscription
(`$share/workers/...`) and spread the load across several instances.

### Dependencies

```python
from typing import Annotated
from mqute import Depends, Message

async def get_db():
    db = await Database.connect()
    try:
        yield db             # the code after yield runs once the handler finishes
    finally:
        await db.close()

def get_device(device_id: str, db: Annotated[Database, Depends(get_db)]) -> Device:
    return db.devices[device_id]

@app.subscribe("devices/{device_id}/telemetry")
async def telemetry(device: Annotated[Device, Depends(get_device)], reading: Reading) -> None:
    ...
```

Dependencies can use topic parameters, the `Message`, the payload and other dependencies.
They are cached per message (`Depends(fn, use_cache=False)` opts out).

### Middleware

```python
@app.middleware
async def authenticate(message, call_next):
    if dict(message.user_properties).get("token") != SECRET:
        return None                  # drop the message
    return await call_next(message)  # may also pass a modified message
```

Middleware registered on a `Router` applies only to that router's routes.

### Errors

```python
from mqute import MessageValidationError, Message, Response

@app.exception_handler(MessageValidationError)
async def invalid_payload(message: Message, exc: Exception) -> Response:
    return Response({"error": str(exc)}, topic=f"{message.topic}/errors")
```

Unhandled exceptions are logged on the `mqute` logger and never stop the app.

### Lifecycle

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app):
    app.state.db = await Database.connect()   # app.state holds app-wide resources
    yield
    await app.state.db.close()

app = MQute(lifespan=lifespan)

@app.on_connect          # after every (re)connection
def connected(): ...

@app.on_disconnect       # reason is None for a clean disconnect
def disconnected(reason): ...
```

`on_startup` and `on_shutdown` decorators are available too. Run the app with:

- `mqute run module:app [--broker URL] [--log-level debug]`
- `app.run()`: blocking, stops on SIGINT/SIGTERM after draining in-flight messages
- `async with app: ...` or `await app.serve()`: embed it in an existing event loop, for
  example inside a FastAPI lifespan (see [`examples/fastapi_integration.py`](examples/fastapi_integration.py))

### Testing

```python
from mqute.testing import TestClient

def test_temperature():
    with TestClient(app) as client:
        (reply,) = client.publish("sensors/kitchen/temperature", 20)
        assert reply.topic == "sensors/kitchen/fahrenheit"
        assert reply.json() == {"room": "kitchen", "fahrenheit": 68.0}
```

No broker needed: `TestClient` swaps in an in-memory transport, runs your lifecycle hooks
and re-raises handler exceptions in the test.

## Examples

- [`examples/basic.py`](examples/basic.py): the essentials
- [`examples/hivemq_cloud.py`](examples/hivemq_cloud.py): HiveMQ Cloud, routers, Pydantic and dependencies
- [`examples/fastapi_integration.py`](examples/fastapi_integration.py): one process serving HTTP and MQTT

## Contributing

Contributions are welcome. Every change starts as an issue, lives on its own branch and lands
through a pull request. See [CONTRIBUTING.md](CONTRIBUTING.md) for the workflow, local setup
and release process.

## License

MQute is licensed under the [GNU GPL v3.0 or later](LICENSE).
