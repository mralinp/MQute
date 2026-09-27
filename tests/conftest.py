import pytest

from mqute import MQute
from mqute.testing import MemoryTransport, TestClient


@pytest.fixture
def app() -> MQute:
    return MQute("mqtt://localhost", transport=MemoryTransport())


@pytest.fixture
def client(app: MQute):
    """A running TestClient; register routes on ``app`` before requesting it."""
    with TestClient(app) as test_client:
        yield test_client
