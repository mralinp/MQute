from typing import Dict, Callable, Any
import paho.mqtt.client as mqtt

from .credentials import Credential
from .router import Router
from .request import Request

class MQuteRequest(Request):
    """
    Represents an MQTT request within the MQute framework.
    Extends the base Request class to include MQTT-specific context such as userdata.
    
    Args:
        path (str): The MQTT topic path.
        userdata (Any): User-defined data passed to the MQTT client.
        payload (Any): The message payload received.
        resolve (Callable): A callback to send a response back to the client.
    """
    def __init__(self, path: str, userdata: Any, payload: Any, resolve: Callable):
        super(self).__init__(path, payload, resolve)
        self.userdata = userdata

class MQute (Router):
    
    
    """
    Main class for the MQute MQTT application framework.
    Handles MQTT client setup, event registration, message routing, and broker communication.
    
    Args:
        url (str): The MQTT broker URL or IP address.
        port (int): The port to connect to on the MQTT broker.
        credentials (Credential): Credentials object for authentication.
    
    Attributes:
        client (mqtt.Client): The underlying Paho MQTT client instance.
    """
    def __init__(self, url: str, port: int, credentials: Credential):
        """
        Initialize the MQute application, set up the MQTT client, and prepare event handlers.
        """
        super().__init__(prefix="")
        self.__url = url
        self.__port = port
        self.__credentials = credentials
        self.__event_handlers: Dict[str, Callable] = {}
        self.__client = self.__create_client()
        
        # Set up message handler
        self.__client.on_message = self.__on_message
        
        # Reattach any existing event handlers
        for event_name, handler in self.__event_handlers.items():
            setattr(self.__client, event_name, handler)
    
    
    def sub(self, path):
        """
        Subscribe to an MQTT topic and register it with the router.
        Args:
            path (str): The topic to subscribe to.
        """
        self.__client.subscribe(path, qos=0)
        super().sub(path)
    
        
    def include_router(self, router: Router, prefix: str = "") -> None:
        """
        Include another router and subscribe to its topic prefix.
        Args:
            router (Router): The router to include.
            prefix (str): Optional prefix for the router's topics.
        """
        super().include_router(router, prefix)
        self.__client.subscribe(f"{prefix}{router.prefix}", qos=1)
        
    
    def on_connect(self):
        """
        Decorator for handling MQTT connect events.
        Returns:
            Callable: A decorator for the connect event handler.
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
        Returns:
            Callable: A decorator for the disconnect event handler.
        """
        def decorator(handler: Callable) -> Callable:
            self.__event_handlers['on_disconnect'] = handler
            if self.__xclient:
                self.__client.on_disconnect = handler
            return handler
        return decorator
    
    
    def on_publish(self):
        """
        Decorator for handling MQTT publish events.
        Returns:
            Callable: A decorator for the publish event handler.
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
        Returns:
            Callable: A decorator for the subscribe event handler.
        """
        def decorator(handler: Callable) -> Callable:
            self.__event_handlers['on_subscribe'] = handler
            if self.__client:
                self.__client.on_subscribe = handler
            return handler
        return decorator
    
    
    def __on_message(self, client, userdata, message):
        """
        Internal handler for incoming MQTT messages. Wraps the message in an MQuteRequest and routes it.
        Args:
            client (mqtt.Client): The MQTT client instance.
            userdata (Any): User-defined data.
            message (MQTTMessage): The received message object.
        """
        topic = message.topic
        payload = message.payload
        print("Recived A message")
        # Try each router in order
        request = MQuteRequest(
            path=topic,
            userdata=userdata,
            payload=payload,
            resolve=lambda response: client.publish(topic, response.to_string(), qos=1, retain=False),
        )
        self.route(request)


    def __create_client(self):
        """
        Create and configure the MQTT client based on provided credentials.
        Returns:
            mqtt.Client: The configured MQTT client instance.
        """
        client = None
        if self.__credentials:
            client = self.__credentials.create_client()
        else:
            client = mqtt.Client()
            
        return client
    
    
    def start(self) -> None:
        """
        Connect to the MQTT broker and start the network loop.
        Raises:
            ConnectionError: If connection to the broker fails.
        """
        print(self.__url, self.__port)
        """Connect to the MQTT broker"""
        try:
            self.__client.connect(self.__url, self.__port)
            self.__client.loop_forever()
        except Exception as e:
            raise ConnectionError(f"Failed to connect to MQTT broker: {str(e)}")
    
    
    def disconnect(self) -> None:
        """
        Disconnect from the MQTT broker and stop the network loop.
        """
        self.__client.loop_stop()
        self.__client.disconnect()
    
    
    def publish(self, topic: str, payload: Any, qos: int = 0, retain: bool = False) -> None:
        """
        Publish a message to a specific MQTT topic.
        Args:
            topic (str): The topic to publish to.
            payload (Any): The message payload.
            qos (int): Quality of Service level (default: 0).
            retain (bool): Whether to retain the message (default: False).
        """
        self.__client.publish(topic, payload, qos=qos, retain=retain)
        
        
    @property
    def client(self) -> mqtt.Client:
        """
        Get the underlying MQTT client instance.
        Returns:
            mqtt.Client: The MQTT client.
        """
        return self.__client