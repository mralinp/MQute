# MQute

<p align="center">

<img src="/assets/cute-modern.png" width="50%" />

</p>

**MQute** is a minimal, async-first MQTT framework for Python — inspired by FastAPI, built on top of `paho-mqtt`.  
It lets you define MQTT topic handlers with decorators, parse payloads with Pydantic, and focus on clean, expressive code.

> **MQute = MQ(TT) + Cuteness** — because MQTT can be elegant, too.

---

## ✨ Features

- 🧭 **Decorator-based routing** like `@app.sub("topic")`
- ⚡ **Async-first**, powered by `asyncio` and `paho-mqtt`
- 🧪 **Typed payload parsing** via `pydantic`
- 🎛️ **Startup/shutdown hooks**
- 🔌 **Pluggable** and lightweight core
- 🐍 **Pure Python**, no external broker dependencies

---

## 🚀 Quick Start

### 📦 Installation (Coming soon)

```bash
pip install mqute
```

### 🎯 Basic Usage

```python
from mqute import MQute, Router, JsonResponse
from mqute.credentials import UserPassCredential
from pydantic import BaseModel

BROKER_URL = "mqtt://test.hivemq.com"
# Create a router instance
app = MQute(
    url=BROKER_URL,
    port=1883,
    # Use UserPassCredential for authentication
    credentials=UserPassCredential(
        client_id="headquarter",
        username="admin",
        password="password"
    ))

# Define your payload model
class SensorData(BaseModel):
    temperature: float
    humidity: int

@app.on_connect()
def on_connect():
    print("Print connected!")

@app.on_disconnect()
def on_disconnect(status):
    print(f"Disconnected error: {status.error}")


# Subscribe to a topic
@app.sub("sensors/+/data")
async def handle_sensor_data(request):
    # Parse the payload
    data = await request.json(SensorData)

    # Process the data
    print(f"Received data from {request.topic}: {data}")

    # Return a response
    return JsonResponse({"status": "received"})

salon_router = Router(prefix="/salon")

@salon_router.sub("/{deviceID}")
def device_handler(request, deviceID: str):
    print (f"received data from device {deviceID}")
    return JsonResponse({"status": "received"})

app.include_router(salon_router, prefix="/device")

app.start()
```

### 🔧 Development Setup

1. Clone the repository:

```bash
git clone https://github.com/mralinp/mqute.git
cd mqute
```

2. Create and activate a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install development dependencies:

```bash
pip install -e ".[dev]"
```

4. Run tests:

```bash
pytest tests/
```

## 📚 Documentation

📖 Coming soon at: https://mralinp.github.io/mqute
Or check out the examples/ directory.

## 🧩 Coming Soon

- Wildcard topic support (#, +)
- QoS management
- HTTP + MQTT hybrid apps
- Pydantic validation error handling
- Auto reconnect & retry logic

## 🧪 Testing

```bash
pytest tests/
```

## 🧑‍💻 Contributing

Pull requests, issues, and ideas are welcome!
If you'd like to contribute, please see `CONTRIBUTING.md` (coming soon).

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⭐ Star MQute if you like cute things and clean MQTT code!

Made with 💙 by Ali
