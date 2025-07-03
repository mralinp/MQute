from typing import Optional
import paho.mqtt.client as paho

from .base import Credential


class UserPassCredential(Credential):
    '''
    Username and password based credentials used for MQTT authentication.
    
    Args:
        client_id (str): Unique identifier for the MQTT client.
        username (Optional[str]): Username for MQTT authentication.
        password (Optional[str]): Password for MQTT authentication.
        tls (bool): Whether to use TLS for the connection. Defaults to False.
    '''
    
    def __init__(
        self,
        client_id: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ):
        self._client_id = client_id
        self._username = username
        self._password = password
    
    def create_client(self) -> paho.Client:
        client = paho.Client(client_id=self._client_id, userdata=None, protocol=paho.MQTTv5)
        if self._username and self._password:
            client.username_pw_set(
                username=self._username,
                password=self._password
            )
        return client 