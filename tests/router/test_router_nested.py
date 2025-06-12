import pytest
from mqute import Router, Request, Response, JsonResponse, ErrorResponse

def test_nested_router_prefixes():
    # Create a router with prefix "building1"
    building_router = Router(prefix="/building1")
    floor_router = Router(prefix="/floor1")
    
    @floor_router.sub("/room/status")
    def handle(request: Request):
        response = JsonResponse({
            "status": 200,
            "payload": request.payload   
        })
        return response
    
    # Include floor router in building router with prefix "floors"
    building_router.include_router(floor_router, include_prefix="/floors")
    
    router = Router()
    # Include building router in main router with prefix "buildings"
    router.include_router(building_router, include_prefix="/buildings")
    
    responses = []
    def handle_response(response: Response):
        responses.append(response)
    
    # This should match "/buildings/building1/floors/floor1/room/status"
    request = Request(
        "/buildings/building1/floors/floor1/room/status",
        {"occupied": True},
        resolve=handle_response
    )
    router.route(request)
    assert len(responses) == 1
    assert isinstance(responses[0], JsonResponse)
    assert responses[0].data["status"] == 200
    assert responses[0].data["payload"]["occupied"] is True