from mqute import Router, Request, Response, JsonResponse

def test_sub():
    print("Testing basic route creation and handling")
    # Create a router with no prefix
    router = Router("")
    @router.sub("/main")
    def handle_main(request: Request):
        return JsonResponse({
            "status": 200,
            "message": request.payload
            })
    
    responses = []
    def handle_response(response: Response):
        responses.append(response)
    
    request = Request("/main", {"message": "hi"}, resolve=handle_response)
    router.route(request)
    
    assert len(responses) == 1
    print(responses[0])
    assert isinstance(responses[0], JsonResponse)
    assert responses[0].data["status"] == 200
    assert responses[0].data["message"] == request.payload
    
    responses.clear()
    
    print("Testing route with prefix")
    router = Router(prefix="/test")
    @router.sub("/path")
    def handler_path(request: Request):
        return JsonResponse({
            "status": 200,
            "message": request.payload
        })
        
    request = Request("/path", {"message": "hello"}, resolve=handle_response)
    router.route(request)
    
    assert isinstance(responses[0], JsonResponse)
    assert responses[0].data["status"] == 200
    assert responses[0].data["message"] == request.payload
    
    responses.clear()

    print("Testing route with prefix and subpath")
    router = Router(prefix="")
    
    @router.sub("devices/camera/status")
    def handle_camera_status(request: Request):
        return JsonResponse(data={"status": 200, "payload": request.payload})
    
    @router.sub("sensors/temperature")
    def handle_temperature(request: Request):
        return JsonResponse(data={"status": 200, "payload": request.payload})
    # Test paths
    request1 = Request("devices/camera/status", {"temp": 25}, resolve=handle_response)
    router.route(request1)
    assert len(responses) == 1
    assert isinstance(responses[0], JsonResponse)
    assert responses[0].data["status"] == 200
    assert responses[0].data["payload"]["temp"] == 25
    responses.clear()
    request2 = Request("sensors/temperature", {"value": 30}, resolve=handle_response)
    router.route(request2)
    assert len(responses) == 1
    assert isinstance(responses[0], JsonResponse)
    assert responses[0].data["status"] == 200
    assert responses[0].data["payload"]["value"] == 30
    responses.clear()
    
    print("Testing non-matching path")
    request3 = Request("devices/camera/unknown", {}, resolve=handle_response)
    router.route(request3)
    assert len(responses) == 1
    assert isinstance(responses[0], Response)
    assert responses[0].error == "No handler registered for path: devices/camera/unknown"
    responses.clear()
    print("Test completed successfully")
    
    print("Testing router with branched paths")
    # Create a router with prefix "devices"
    router = Router(prefix="")
    
    @router.sub("/devices/camera/status")
    def handle_camera_status(request: Request):
        return JsonResponse(data={"status": "camera", "payload": request.payload})
    
    @router.sub("/devices/sensors/temperature")
    def handle_temperature(request: Request):
        return JsonResponse(data={"status": "temperature", "payload": request.payload})
    
    # Test paths
    request1 = Request("devices/camera/status", {"temp": 25}, resolve=handle_response)
    router.route(request1)
    assert len(responses) == 1
    assert isinstance(responses[0], JsonResponse)
    assert responses[0].data["status"] == "camera"
    assert responses[0].data["payload"]["temp"] == 25
    responses.clear()
    request2 = Request("devices/sensors/temperature", {"value": 30}, resolve=handle_response)
    router.route(request2)
    assert len(responses) == 1
    assert isinstance(responses[0], JsonResponse)
    assert responses[0].data["status"] == "temperature"
    assert responses[0].data["payload"]["value"] == 30
    responses.clear()
    print("Test completed successfully")
    
    