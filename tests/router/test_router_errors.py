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
            request.resolve_request(ErrorResponse(error="Value must be an integer"))
            return
        request.resolve_request(JsonResponse(data={"value": request.payload["value"]}))

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
    
    # Test including router with invalid prefix
    with pytest.raises(RuntimeError) as exc_info:
        router.include_router(None)
    assert "Failed to include router" in str(exc_info.value)

    # Test including router with duplicate paths
    sub_router1 = Router()
    sub_router2 = Router()
    
    @sub_router1.sub("test/path")
    def handler1(request: Request):
        pass
    
    @sub_router2.sub("test/path")
    def handler2(request: Request):
        pass
    
    router.include_router(sub_router1)
    with pytest.raises(RuntimeError) as exc_info:
        router.include_router(sub_router2)
    assert "Failed to include router" in str(exc_info.value)

def test_router_with_validation_middlewares():
    router = Router()
    responses = []

    def handle_response(response: Response):
        responses.append(response)

    @router.middleware
    def validate_payload(request: Request) -> None:
        if not isinstance(request.payload, dict):
            request.resolve_request(ErrorResponse(error="Payload must be a dictionary"))
        elif "required_field" not in request.payload:
            request.resolve_request(ErrorResponse(error="Missing required field"))

    @router.sub("test/validation")
    def handle_validation(request: Request):
        request.resolve_request(JsonResponse(data=request.payload))

    # Test invalid payload type
    request = Request("test/validation", "not a dict", resolve=handle_response)
    router.route(request)
    assert len(responses) == 1
    assert isinstance(responses[0], ErrorResponse)
    assert "Payload must be a dictionary" in responses[0].error

    # Test missing required field
    responses.clear()
    request = Request("test/validation", {}, resolve=handle_response)
    router.route(request)
    assert len(responses) == 1
    assert isinstance(responses[0], ErrorResponse)
    assert "Missing required field" in responses[0].error

    # Test valid payload
    responses.clear()
    request = Request("test/validation", {"required_field": "value"}, resolve=handle_response)
    router.route(request)
    assert len(responses) == 1
    assert isinstance(responses[0], JsonResponse)
    assert responses[0].data["required_field"] == "value" 