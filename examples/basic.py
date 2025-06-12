from mqute import MQute, Router, JsonResponse
from pydantic import BaseModel

BrokerUrl = "test.hivmq.com"

# Create a router instance
app = MQute(
    url=BROKER_URL,
    credentials=UserPassCredential(
        client_id="headquarter",
        username="admin",
        password="password"
    ))

# Define your payload model
class SensorData(BaseModel):
    temperature: float
    humidity: int

@app.on_connect
def on_connect():
    print("Print connected!")

@app.on_disconnect
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

@device_router.sub("/{deviceID}")
def device_handler(request, deviceID: str):
    print (f"received data from device {deviceID}")
    return JsonResponse({"status": "received"})

app.include_router(device_router, prefix="/device")

app.start()