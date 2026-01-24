from typing import Dict, Callable, Optional, List, Tuple

from .request import Request


class Router:
    """
    The Router class is responsible for managing URL paths, handlers, and middleware.
    It allows for organizing code into modular, prefixed routes and including
    sub-routers for better structure.

    Args:
        prefix (str): An optional prefix for all routes defined in this router.
    """
    def __init__(self, prefix: str = ""):
        """
        Initializes the Router instance.

        Args:
            prefix (str): A URL prefix for all routes in this router.
        """
        # Remove leading/trailing slashes and normalize
        self.__prefix = prefix.strip('/')
        self.__middlewares: List[Callable] = []
        self.__handlers: Dict[str, Callable] = {}
    
    
    @property
    def prefix(self) -> str:
        """The URL prefix for this router."""
        return self.__prefix


    def middleware(self, middleware_func: Callable):
        """
        Decorator to add middleware to the router.

        Middleware functions are executed for every request that this router handles,
        before the main handler is called. They can modify the request or raise
        an exception to stop processing.

        Args:
            middleware_func (Callable): The middleware function to add.
        """
        self.__middlewares.append(middleware_func)
        return middleware_func


    def _run_middlewares(self, request: Request) -> None:
        """
        Run all registered middlewares in the order they were added.

        A middleware can either return a (potentially modified) request object to
        continue processing, or raise an exception to halt the request and
        trigger a rejection.

        Args:
            request (Request): The incoming request to process.
        """
        for middleware in self.__middlewares:
            try:
                request = middleware(request)
            except Exception as e:
                request.reject(str(e))
                return


    def _normalize_path(self, path: str) -> str:
        """Normalize a path by removing leading/trailing slashes and empty segments"""
        return '/'.join(segment for segment in path.split('/') if segment)


    def _get_handler(self, path: str) -> Optional[Callable]:
        """
        Retrieves the handler function for a given path.

        The path is normalized and combined with the router's prefix to find
        the corresponding handler.

        Args:
            path (str): The path to find a handler for.

        Returns:
            Optional[Callable]: The handler function if found, otherwise None.
        """
        # Normalize the input path
        normalized_path = self._normalize_path(path)
        full_path = self._normalize_path(f"{self.__prefix}/{normalized_path}")
        return self.__handlers.get(full_path)


    def _execute_handler(self, request: Request, handler: Callable) -> None:
        """
        Executes the handler for a given request.

        This method calls the handler and resolves or rejects the request based on
        the outcome.

        Args:
            request (Request): The request to handle.
            handler (Callable): The handler function to execute.
        """
        try:
            response = handler(request)
            request.resolve_request(response)
        except Exception as e:
            request.reject(str(e))


    def sub(self, path: str):
        """
        Decorator to register a request handler for a specific sub-path.

        Args:
            path (str): The sub-path to register the handler for.
        """
        def decorator(handler: Callable):
            # Normalize the path
            normalized_path = self._normalize_path(path)
            full_path = self._normalize_path(f"{self.__prefix}/{normalized_path}")
            self.__handlers[full_path] = handler
            return handler
        return decorator


    def route(self, request: Request) -> None:
        """
        Routes an incoming request to the appropriate handler.

        This method first runs all registered middlewares. If the request is not
        resolved or rejected by a middleware, it finds and executes the
        handler for the request's path.

        Args:
            request (Request): The request to route.
        """
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


    def include_router(self, router: 'Router', prefix: Optional[str] = None) -> None:
        """
        Includes another router's handlers into this one, with an optional prefix.

        This is useful for modularizing an application into smaller, reusable
        router components.

        Args:
            router (Router): The router instance to include.
            prefix (Optional[str]): An optional prefix for the included router's paths.
        
        Raises:
            RuntimeError: If there's an issue including the router.
        """
        try:
            # Normalize all prefixes
            router_prefix = self._normalize_path(router.prefix)
            if prefix is not None:
                prefix = self._normalize_path(prefix)
                final_prefix = self._normalize_path(f"{prefix}/{router_prefix}")
            else:
                final_prefix = router_prefix

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
                self.__handlers[new_path] = handler

        except Exception as e:
            raise RuntimeError(f"Failed to include router: {str(e)}")
    
    