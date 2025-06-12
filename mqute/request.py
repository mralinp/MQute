from dataclasses import dataclass
from typing import Any, Callable

from .response import Response, ErrorResponse


@dataclass
class Request:
    """Represents an MQTT request with payload and response handling"""
    path: str
    payload: Any  # No validation, can be any type
    resolve: Callable[[Response], None]
    _resolved: bool = False

    def resolve_request(self, response: Response) -> None:
        """Resolve the request with any Response type"""
        if self._resolved:
            raise RuntimeError("Request already resolved")
        self._resolved = True
        self.resolve(response)

    def reject(self, error: str) -> None:
        """Reject the request with an error message"""
        if self._resolved:
            raise RuntimeError("Request already resolved")
        self._resolved = True
        self.resolve(ErrorResponse(error=error))

    @property
    def is_resolved(self) -> bool:
        return self._resolved
