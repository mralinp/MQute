from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class Response(ABC):
    """Base class for all responses"""
    @abstractmethod
    def to_string(self) -> str:
        """Convert response to string format"""
        pass


@dataclass
class JsonResponse(Response):
    """JSON response type"""
    data: Dict[str, Any]

    def to_string(self) -> str:
        return str(self.data)


@dataclass
class ErrorResponse(Response):
    """Error response type"""
    error: str

    def to_string(self) -> str:
        return f"Error: {self.error}"
