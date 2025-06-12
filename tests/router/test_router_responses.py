import pytest
from mqute import Router, Request, Response, JsonResponse, ErrorResponse
from dataclasses import dataclass

@dataclass
class CustomResponse(Response):
    custom_field: str
    
    def to_string(self):
        return self.custom_field

def test_router_response_handling():
    router = Router()
    responses = []

    def handle_response(response: Response):
        responses.append(response)

    @router.sub("test/json")
    def handle_json(request: Request):
        return JsonResponse(data={"message": "success"})

    @router.sub("test/error")
    def handle_error(request: Request):
        return ErrorResponse(error="test error")

    @router.sub("test/custom")
    def handle_custom(request: Request):
        return CustomResponse(custom_field="test")

    # Test JSON response
    request = Request("test/json", {}, resolve=handle_response)
    router.route(request)
    assert len(responses) == 1
    assert isinstance(responses[0], JsonResponse)
    assert responses[0].data["message"] == "success"

    # Test error response
    responses.clear()
    request = Request("test/error", {}, resolve=handle_response)
    router.route(request)
    assert len(responses) == 1
    assert isinstance(responses[0], ErrorResponse)
    assert responses[0].error == "test error"

    # Test custom response
    responses.clear()
    request = Request("test/custom", {}, resolve=handle_response)
    router.route(request)
    assert len(responses) == 1
    assert isinstance(responses[0], CustomResponse)
    assert responses[0].custom_field == "test"

def test_custom_response_type():
    router = Router()
    responses = []

    def handle_response(response: Response):
        responses.append(response)

    @dataclass
    class TemperatureResponse(Response):
        temperature: float
        unit: str

        def to_string(self):
            return f"{self.temperature} {self.unit}"
        
    @router.sub("temperature")
    def handle_temperature(request: Request):
        return TemperatureResponse(
            temperature=25.5,
            unit="celsius"
        )
    

    request = Request("temperature", {}, resolve=handle_response)
    router.route(request)
    assert len(responses) == 1
    print(responses[0])
    assert isinstance(responses[0], TemperatureResponse)
    assert responses[0].temperature == 25.5
    assert responses[0].unit == "celsius" 