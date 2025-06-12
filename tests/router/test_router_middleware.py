import pytest
from mqute import Router, Request, Response, JsonResponse, ErrorResponse

def test_router_middleware():
    router = Router()
    responses = []

    def handle_response(response: Response):
        responses.append(response)

    # Middleware that adds a timestamp
    @router.middleware
    def add_timestamp(request: Request) -> None:
        if not request.is_resolved:
            request.payload['timestamp'] = '2024-03-20T12:00:00Z'

    # Middleware that validates temperature
    @router.middleware
    def validate_temperature(request: Request) -> None:
        if request.path.endswith('/temperature'):
            if 'value' not in request.payload:
                request.resolve_request(ErrorResponse(error="Missing temperature value"))
            elif not isinstance(request.payload['value'], (int, float)):
                request.resolve_request(ErrorResponse(error="Temperature value must be a number"))
            elif not -50 <= request.payload['value'] <= 100:
                request.resolve_request(ErrorResponse(error="Temperature out of range"))

    # Handler for temperature
    @router.sub("devices/temperature")
    def handle_temperature(request: Request) -> None:
        request.resolve_request(JsonResponse(data={
            "status": "received",
            "data": request.payload
        }))

    # Test valid temperature
    request = Request(
        path="devices/temperature",
        payload={"value": 25},
        resolve=handle_response
    )
    router.route(request)
    assert len(responses) == 1
    assert isinstance(responses[0], JsonResponse)
    assert responses[0].data["status"] == "received"
    assert "timestamp" in responses[0].data["data"]
    assert responses[0].data["data"]["value"] == 25

    # Test missing value
    responses.clear()
    request = Request(
        path="devices/temperature",
        payload={},
        resolve=handle_response
    )
    router.route(request)
    assert len(responses) == 1
    assert isinstance(responses[0], ErrorResponse)
    assert "Missing temperature value" in responses[0].error

    # Test out of range
    responses.clear()
    request = Request(
        path="devices/temperature",
        payload={"value": 150},
        resolve=handle_response
    )
    router.route(request)
    assert len(responses) == 1
    assert isinstance(responses[0], ErrorResponse)
    assert "Temperature out of range" in responses[0].error

    # Test wrong type
    responses.clear()
    request = Request(
        path="devices/temperature",
        payload={"value": "hot"},
        resolve=handle_response
    )
    router.route(request)
    assert len(responses) == 1
    assert isinstance(responses[0], ErrorResponse)
    assert "Temperature value must be a number" in responses[0].error 