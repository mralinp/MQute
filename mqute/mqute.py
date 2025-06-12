from typing import Dict, Callable, Any, List
import paho.mqtt.client as mqtt
import threading

from .credentials import Credential
from .router import Router
from .request import Request

class MQuteRequest(Request):
    def __init__(self, path: str, userdata: Any, payload: Any, resolve: Callable):
        super().__init__(path, payload, resolve)
        self.userdata = userdata

class MQute (Router):
    def __init__(self, url: str, port: int, credentials: Credential):
        self.__url = url
        self.__port = port
        self.__credentials = credentials
        self.__client = self.__create_client()
        self.__event_handlers: Dict[str, Callable] = {}
        
    
    def on_connect(self):
        """
        Decorator for handling MQTT connect events.
        
        Usage:
            @broker.on_connect()
            def handle_connect(client, userdata, flags, rc):
                print(f"Connected with result code: {rc}")
        """
        def decorator(handler: Callable) -> Callable:
            self.__event_handlers['on_connect'] = handler
            if self.__client:
                self.__client.on_connect = handler
            return handler
        return decorator
    
    def on_disconnect(self):
        """
        Decorator for handling MQTT disconnect events.
        
        Usage:
            @broker.on_disconnect()
            def handle_disconnect(client, userdata, rc):
                print(f"Disconnected with result code: {rc}")
        """
        def decorator(handler: Callable) -> Callable:
            self.__event_handlers['on_disconnect'] = handler
            if self.__client:
                self.__client.on_disconnect = handler
            return handler
        return decorator
    
    def on_publish(self):
        """
        Decorator for handling MQTT publish events.
        
        Usage:
            @broker.on_publish()
            def handle_publish(client, userdata, mid):
                print(f"Message {mid} published")
        """
        def decorator(handler: Callable) -> Callable:
            self.__event_handlers['on_publish'] = handler
            if self.__client:
                self.__client.on_publish = handler
            return handler
        return decorator
    
    def on_subscribe(self):
        """
        Decorator for handling MQTT subscribe events.
        
        Usage:
            @broker.on_subscribe()
            def handle_subscribe(client, userdata, mid, granted_qos):
                print(f"Subscribed with QoS: {granted_qos}")
        """
        def decorator(handler: Callable) -> Callable:
            self.__event_handlers['on_subscribe'] = handler
            if self.__client:
                self.__client.on_subscribe = handler
            return handler
        return decorator
    
    def __on_message(self, client, userdata, message):
        """Handle incoming MQTT messages and route them to appropriate handlers"""
        topic = message.topic
        payload = message.payload
        # Try each router in order
        request = MQuteRequest(
            path=topic,
            userdata=userdata,
            payload=payload,
            resolve=lambda response: client.publish(topic, response.to_string(), qos=1, retain=False),
        )
        self.route(request)

    def __create_client(self):
        """Create and configure the MQTT client based on credentials"""
        client = None
        if self.__credentials:
            client = self.__credentials.create_client()
            print("Here!!!!")
        else:
            client = mqtt.Client()
        
        # Set up message handler
        client.on_message = self.__on_message
        
        # Reattach any existing event handlers
        for event_name, handler in self.__event_handlers.items():
            setattr(client, event_name, handler)
        return client
    
    def connect(self) -> None:
        """Connect to the MQTT broker"""
        try:
            self.__client.connect_async(self.__url, self.__port)
            thread = threading.Thread(target=self.__client.loop_forever, daemon=True)
            thread.start()
        except Exception as e:
            raise ConnectionError(f"Failed to connect to MQTT broker: {str(e)}")
    
    def disconnect(self) -> None:
        """Disconnect from the MQTT broker"""
        self.__client.loop_stop()
        self.__client.disconnect()
    
    def publish(self, topic: str, payload: Any, qos: int = 0, retain: bool = False) -> None:
        """Publish a message to a topic"""
        self.__client.publish(topic, payload, qos=qos, retain=retain)
        
    @property
    def client(self) -> mqtt.Client:
        """Get the underlying MQTT client instance"""
        return self.__client