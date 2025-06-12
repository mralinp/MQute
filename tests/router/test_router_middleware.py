import pytest
from mqute import Router, Request, Response, JsonResponse, ErrorResponse

@pytest.fixture
def router():
    router = Router()
    
    @router.middleware
    def add_timestamp(request: Request):
        request.payload['timestamp'] = '2024-03-20T12:00:00Z'
        return request

    @router.middleware
    def validate_temperature(request: Request):
        if request.path.endswith('/temperature'):
            if 'value' not in request.payload:
                raise Exception("Missing temperature value")
            elif not isinstance(request.payload['value'], (int, float)):
                raise Exception("Temperature value must be a number")
            elif not -50 <= request.payload['value'] <= 100:
                raise Exception("Temperature out of range")
        return request

    @router.sub("devices/temperature")
    def handle_temperature(request: Request) -> Response:
        return JsonResponse(data={
            "status": "received",
            "data": request.payload
        })
    
    return router

@pytest.fixture
def handle_response():
    responses = []
    def callback(response: Response):
        responses.append(response)
    return callback, responses

def test_valid_temperature(router, handle_response):
    callback, responses = handle_response
    request = Request(
        path="devices/temperature",
        payload={"value": 25},
        resolve=callback
    )
    router.route(request)
    assert len(responses) == 1
    assert isinstance(responses[0], JsonResponse)
    assert responses[0].data["status"] == "received"
    assert "timestamp" in responses[0].data["data"]
    assert responses[0].data["data"]["value"] == 25

def test_missing_temperature_value(router, handle_response):
    callback, responses = handle_response
    request = Request(
        path="devices/temperature",
        payload={},
        resolve=callback
    )
    router.route(request)
    assert len(responses) == 1
    assert isinstance(responses[0], ErrorResponse)
    assert "Missing temperature value" in responses[0].error

def test_temperature_out_of_range(router, handle_response):
    callback, responses = handle_response
    request = Request(
        path="devices/temperature",
        payload={"value": 150},
        resolve=callback
    )
    router.route(request)
    assert len(responses) == 1
    assert isinstance(responses[0], ErrorResponse)
    assert "Temperature out of range" in responses[0].error

def test_temperature_wrong_type(router, handle_response):
    callback, responses = handle_response
    request = Request(
        path="devices/temperature",
        payload={"value": "hot"},
        resolve=callback
    )
    router.route(request)
    assert len(responses) == 1
    assert isinstance(responses[0], ErrorResponse)
    assert "Temperature value must be a number" in responses[0].error 