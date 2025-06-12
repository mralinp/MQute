from abc import ABC, abstractmethod
import paho.mqtt.client as mqtt


class Credential(ABC):
    """Abstract base class for MQTT credentials"""
    
    @abstractmethod
    def create_client(self) -> mqtt.Client:
        """
        Create and configure an MQTT client with these credentials
        
        Args:
            client_id: Client ID to use for the MQTT connection
            
        Returns:
            Configured MQTT client instance
        """
        pass 