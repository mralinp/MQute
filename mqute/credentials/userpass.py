from typing import Optional
import paho.mqtt.client as paho
from .base import Credential
import ssl


class UserPassCredential(Credential):
    """Username and password based credentials"""
    
    def __init__(
        self,
        client_id: str,
        username: Optional[str] = None,
        password: Optional[str] = None
    ):
        self._client_id = client_id
        self._username = username
        self._password = password
    
    def create_client(self) -> paho.Client:
        client = paho.Client(client_id=self._client_id, userdata=None, protocol=paho.MQTTv5)
        client.tls_set(tls_version=ssl.PROTOCOL_TLSv1_2)
        if self._username and self._password:
            client.username_pw_set(
                username=self._username,
                password=self._password
            )
        return client 