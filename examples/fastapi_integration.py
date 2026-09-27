"""Run MQute inside a FastAPI app: one process serving HTTP and MQTT.

pip install fastapi uvicorn
uvicorn examples.fastapi_integration:api
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from mqute import MQute

mqtt = MQute("mqtt://localhost:1883")
last_seen: dict[str, str] = {}


@mqtt.subscribe("devices/{device_id}/heartbeat")
async def heartbeat(device_id: str, timestamp: str) -> None:
    last_seen[device_id] = timestamp


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with mqtt:
        yield


api = FastAPI(lifespan=lifespan)


@api.get("/devices/{device_id}")
async def device(device_id: str) -> dict[str, str | None]:
    return {"device_id": device_id, "last_seen": last_seen.get(device_id)}


@api.post("/devices/{device_id}/reboot")
async def reboot(device_id: str) -> dict[str, bool]:
    await mqtt.publish(f"devices/{device_id}/command", {"action": "reboot"}, qos=1)
    return {"queued": True}
