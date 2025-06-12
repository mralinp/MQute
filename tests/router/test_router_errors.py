import pytest
from mqute import Router, Request, Response, JsonResponse, ErrorResponse

def test_router_error_handling():
    router = Router()
    responses = []

    def handle_response(response: Response):
        responses.append(response)

    @router.sub("test/validation")
    def handle_validation(request: Request):
        if not isinstance(request.payload.get("value"), int):
            raise Exception("Value must be an integer")
        return JsonResponse(data={"value": request.payload["value"]})

    # Test validation error
    request = Request("test/validation", {"value": "not an int"}, resolve=handle_response)
    router.route(request)
    assert len(responses) == 1
    assert isinstance(responses[0], ErrorResponse)
    assert "Value must be an integer" in responses[0].error

    # Test successful validation
    responses.clear()
    request = Request("test/validation", {"value": 42}, resolve=handle_response)
    router.route(request)
    assert len(responses) == 1
    assert isinstance(responses[0], JsonResponse)
    assert responses[0].data["value"] == 42

def test_router_inclusion_errors():
    router = Router()
    
    # Test including router with invalid router (None)
    with pytest.raises(RuntimeError) as exc_info:
        router.include_router(None)
    assert "Failed to include router" in str(exc_info.value)

    # Test including router with same paths (should work, last one wins)
    sub_router1 = Router()
    sub_router2 = Router()
    
    @sub_router1.sub("test/path")
    def handler1(request: Request):
        return JsonResponse(data={"handler": "first"})
    
    @sub_router2.sub("test/path")
    def handler2(request: Request):
        return JsonResponse(data={"handler": "second"})
    
    router.include_router(sub_router1)
    router.include_router(sub_router2)  # This should work, not raise an error
    
    # Verify that the second handler takes precedence
    responses = []
    def handle_response(response: Response):
        responses.append(response)
    
    request = Request("test/path", {}, resolve=handle_response)
    router.route(request)
    assert len(responses) == 1
    assert isinstance(responses[0], JsonResponse)
    assert responses[0].data["handler"] == "second"

def test_router_with_validation_middlewares():
    router = Router()
    responses = []

    def handle_response(response: Response):
        responses.append(response)

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
    def handle_temperature(request: Request):
        return JsonResponse(data=request.payload)

    # Test missing temperature value
    request = Request("devices/temperature", {}, resolve=handle_response)
    router.route(request)
    assert len(responses) == 1
    assert isinstance(responses[0], ErrorResponse)
    assert "Missing temperature value" in responses[0].error

    # Test invalid temperature type
    responses.clear()
    request = Request("devices/temperature", {"value": "hot"}, resolve=handle_response)
    router.route(request)
    assert len(responses) == 1
    assert isinstance(responses[0], ErrorResponse)
    assert "Temperature value must be a number" in responses[0].error

    # Test temperature out of range
    responses.clear()
    request = Request("devices/temperature", {"value": 150}, resolve=handle_response)
    router.route(request)
    assert len(responses) == 1
    assert isinstance(responses[0], ErrorResponse)
    assert "Temperature out of range" in responses[0].error

    # Test valid temperature
    responses.clear()
    request = Request("devices/temperature", {"value": 25}, resolve=handle_response)
    router.route(request)
    assert len(responses) == 1
    assert isinstance(responses[0], JsonResponse)
    assert responses[0].data["value"] == 25 