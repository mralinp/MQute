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
