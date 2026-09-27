"""Connect to a HiveMQ Cloud cluster, with routers, pydantic and dependencies.

pip install "mqute[pydantic]"
export HIVEMQ_HOST=xxxx.s1.eu.hivemq.cloud HIVEMQ_USERNAME=... HIVEMQ_PASSWORD=...
python examples/hivemq_cloud.py
"""

import os
from typing import Annotated

from pydantic import BaseModel

from mqute import Depends, MQute, Router, providers

app = MQute(
    providers.hivemq_cloud(
        host=os.environ["HIVEMQ_HOST"],
        username=os.environ["HIVEMQ_USERNAME"],
        password=os.environ["HIVEMQ_PASSWORD"],
    )
)
devices = Router(prefix="devices")


class Command(BaseModel):
    action: str
    value: int | None = None


class Registry:
    def __init__(self) -> None:
        self.known = {"lamp-1", "lamp-2"}


registry = Registry()


def get_registry() -> Registry:
    return registry


@devices.subscribe("{device_id}/command", qos=1, response_topic="devices/{device_id}/ack")
async def command(
    device_id: str,
    cmd: Command,
    registry: Annotated[Registry, Depends(get_registry)],
) -> dict[str, object]:
    if device_id not in registry.known:
        return {"ok": False, "error": "unknown device"}
    return {"ok": True, "action": cmd.action}


app.include_router(devices)

if __name__ == "__main__":
    app.run()
