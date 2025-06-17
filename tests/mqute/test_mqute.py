import os
import pytest
from mqute import MQute, MQuteRequest, Response, JsonResponse
from mqute.credentials import UserPassCredential

@pytest.fixture
def credential():
    username=os.getenv("BROKER_USERNAME")
    password=os.getenv("BROKER_PASSWORD")
    client_id = "headquarter"
    
    return UserPassCredential(client_id, username, password)

@pytest.fixture
def app(credential):
    app = MQute(
        url=os.getenv("BROKER_URL"),
        port=int(os.getenv("BROKER_PORT")),
        credentials=credential
    )
    
    return app

def test_mqute(app):
    
    message = {"message": "hello"}
    
    app.sub("/echo")
    async def handle_test(request: MQuteRequest):
        print(request.payload)
        return JsonResponse(request.payload)

    app.start()
    
    print("im here...")
    
    app.publish("/echo", str(message), 0, False)
    
    
    

    
def test_mqute_initialization():
    # Get environment variables
    broker_url = os.getenv('BROKER_URL')
    broker_username = os.getenv('BROKER_USERNAME')
    broker_password = os.getenv('BROKER_PASSWORD')
    
    # Assert that environment variables are loaded
    assert broker_url is not None, "BROKER_URL not found in environment variables"
    assert broker_username is not None, "BROKER_USERNAME not found in environment variables"
    assert broker_password is not None, "BROKER_PASSWORD not found in environment variables"
    
    # Initialize MQute with the environment variables
    app = MQute(url=broker_url)
    assert app is not None
    
    