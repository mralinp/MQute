from .user_pass import UserPassCredential


class UserPassTLSCredential(UserPassCredential):
    
    def __init__(
        self, 
        client_id:str, 
        username: str = None, 
        password: str = None, 
        cert: str = None
    ):
        super().__init__(client_id=client_id, username=username, password=password)
        self.cert = cert
        
    def create_client(self):
        client = super().create_client()
        client.tls_set(
            ca_certs=self.cert,
            certfile=None,
            keyfile=None,
            cert_reqs=paho.ssl.CERT_REQUIRED,
            tls_version=paho.ssl.PROTOCOL_TLSv1_2,
            ciphers=None
        )
        return client
