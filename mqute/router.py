from typing import Dict, Callable, Any, Optional, List, Union, Tuple, Protocol
from .request import Request



class Router:
    def __init__(self, prefix: str = ""):
        # Remove leading/trailing slashes and normalize
        self.__prefix = prefix.strip('/')
        self.__middlewares: List[Callable] = []
        self.__handlers: Dict[str, Callable] = {}
    
    @property
    def prefix(self) -> str:
        return self.__prefix

    def middleware(self, middleware_func: Callable):
        """Decorator to add middleware to the router"""
        self.__middlewares.append(middleware_func)
        return middleware_func

    def _run_middlewares(self, request: Request) -> None:
        """Run all middlewares in order.
        Middleware should either return (continue) or raise an error (reject)"""
        for middleware in self.__middlewares:
            try:
                request = middleware(request)
            except Exception as e:
                request.reject(str(e))
                return

    def _normalize_path(self, path: str) -> str:
        """Normalize a path by removing leading/trailing slashes and empty segments"""
        return '/'.join(segment for segment in path.split('/') if segment)

    def _get_handler(self, path: str) -> Tuple[Optional[Callable], str]:
        """Get the handler for a path and its full path"""
        # Normalize the input path
        normalized_path = self._normalize_path(path)
        full_path = self._normalize_path(f"{self.__prefix}/{normalized_path}")
        print(f"Looking for handler with path: {path}")
        print(f"Normalized path: {normalized_path}")
        print(f"Full path with prefix: {full_path}")
        print(f"Available handlers: {list(self.__handlers.keys())}")
        handler = self.__handlers.get(full_path)
        print(f"Found handler: {handler != None}")
        return self.__handlers.get(full_path)

    def _execute_handler(self, request: Request, handler: Callable) -> None:
        """Execute a handler for a request"""
        try:
            response = handler(request)
            request.resolve_request(response)
        except Exception as e:
            request.reject(str(e))

    def sub(self, path: str):
        """Decorator to register a handler for a path"""
        def decorator(handler: Callable):
            # Normalize the path
            print("Registering handler for path:", path)
            normalized_path = self._normalize_path(path)
            print("Normalized path:", normalized_path)
            full_path = self._normalize_path(f"{self.__prefix}/{normalized_path}")
            print("Full path with prefix:", full_path)
            self.__handlers[full_path] = handler
            return handler
        return decorator

    def route(self, request: Request) -> None:
        """Route a request through middlewares to the appropriate handler"""
        try:
            # Run middlewares
            self._run_middlewares(request)
            if request.is_resolved:
                return

            # Get and execute handler
            handler = self._get_handler(request.path)
            if handler is None:
                request.reject(f"No handler registered for path: {request.path}")
                return

            self._execute_handler(request, handler)
                
        except Exception as e:
            request.reject(str(e))

    def include_router(self, router: 'Router', include_prefix: Optional[str] = None) -> None:
        """Include another router, optionally with a prefix"""
        try:
            # Normalize all prefixes
            router_prefix = self._normalize_path(router.prefix)
            if include_prefix is not None:
                include_prefix = self._normalize_path(include_prefix)
                final_prefix = self._normalize_path(f"{include_prefix}/{router_prefix}")
            else:
                final_prefix = router_prefix

            print(f"Including router with prefix: {router_prefix}")
            print(f"Final prefix: {final_prefix}")
            print(f"Original handlers: {list(router.__handlers.items())}")

            for path, handler in router.__handlers.items():
                # Remove the router's prefix from the path (by segments, not by string length)
                path_segments = path.split('/')
                prefix_segments = router_prefix.split('/') if router_prefix else []
                # Remove prefix segments from the start of path_segments
                if path_segments[:len(prefix_segments)] == prefix_segments:
                    path_without_prefix_segments = path_segments[len(prefix_segments):]
                else:
                    path_without_prefix_segments = path_segments
                path_without_prefix = '/'.join(path_without_prefix_segments)
                new_path = self._normalize_path(f"{final_prefix}/{path_without_prefix}")
                print(f"Adding handler for path: {new_path}")
                self.__handlers[new_path] = handler

            print(f"Final handlers: {list(self.__handlers.keys())}")
        except Exception as e:
            raise RuntimeError(f"Failed to include router: {str(e)}")
    
    