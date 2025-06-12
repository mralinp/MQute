import pytest
from mqute import Router, Request, Response, JsonResponse, ErrorResponse

@pytest.fixture
def router():
    router = Router(prefix="")
    @router.sub("x/y/z")
    def handle(request: Request):
        request.resolve_request(JsonResponse(data={"status": 200, "message": request.payload}))
    return router

def test_nested_router_prefixes(router):
    # Create a router with prefix "building1"
    building_router = Router(prefix="/building1")
    floor_router = Router(prefix="/floor1")
    
    @floor_router.sub("/room/status")
    def handle(request: Request):
        response = JsonResponse({
            "status": 200,
            "payload": request.payload   
        })
        request.resolve_request(response)
    
    # Include floor router in building router with prefix "floors"
    building_router.include_router(floor_router, include_prefix="/floors")
    
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

def test_nested_router_middleware():
    # Sub-router for buildings
    building_router = Router(prefix="buildings")
    responses = []

    def handle_response(response: Response):
        responses.append(response)

    # Middleware on building router: only allow status "active" or "inactive"
    @building_router.middleware
    def validate_building_status(request: Request) -> None:
        if request.path.endswith('/status'):
            if request.payload.get("status") not in ["active", "inactive"]:
                request.resolve_request(ErrorResponse(error="Invalid building status"))

    # Handler for building status (no wildcard)
    @building_router.sub("building1/status")
    def handle_building_status(request: Request) -> None:
        request.resolve_request(JsonResponse(data={
            "status": "received",
            "data": request.payload
        }))

    # Main router with a middleware that adds a request_id
    main_router = Router()
    @main_router.middleware
    def add_request_id(request: Request) -> None:
        if not request.is_resolved:
            request.payload["request_id"] = "123"

    # Include the building router
    main_router.include_router(building_router)

    # Test valid status
    request = Request(
        path="buildings/building1/status",
        payload={"status": "active"},
        resolve=handle_response
    )
    main_router.route(request)
    assert len(responses) == 1
    assert isinstance(responses[0], JsonResponse)
    assert responses[0].data["status"] == "received"
    assert responses[0].data["data"]["status"] == "active"
    assert responses[0].data["data"]["request_id"] == "123"

    # Test invalid status
    responses.clear()
    request = Request(
        path="buildings/building1/status",
        payload={"status": "unknown"},
        resolve=handle_response
    )
    main_router.route(request)
    assert len(responses) == 1
    assert isinstance(responses[0], ErrorResponse)
    assert "Invalid building status" in responses[0].error 