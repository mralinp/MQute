"""The smallest useful MQute app.

mosquitto -p 1883 &
mqute run examples.basic:app
mosquitto_pub -t sensors/kitchen/temperature -m '{"celsius": 21.5}'
"""

from dataclasses import dataclass

from mqute import MQute

app = MQute("mqtt://localhost:1883")


@dataclass
class Reading:
    celsius: float


@app.on_connect
def connected() -> None:
    print("connected")


@app.subscribe("sensors/{room}/temperature", response_topic="sensors/{room}/fahrenheit")
async def temperature(room: str, reading: Reading) -> dict[str, float | str]:
    return {"room": room, "fahrenheit": reading.celsius * 9 / 5 + 32}


if __name__ == "__main__":
    app.run()
