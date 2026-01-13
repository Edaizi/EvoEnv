from typing import Any, Dict
from virtual_server.base_server import BaseServer

SERVER_REGISTRY: Dict[str, BaseServer] = {}

def register_server(server_name: str):
    """
    a decorator for server registry
    
    Example:
        @register_server("MyServer")
        class MyServer(BaseServer):
            ...
    """
    def decorator(cls: Any) -> Any:
        if server_name in SERVER_REGISTRY:
            raise ValueError(f"Warning: Server '{server_name}' has already been registed")
        SERVER_REGISTRY[server_name] = cls
        return cls
    return decorator


def create_server(server_name: str, **kwargs: Any) -> Any:
    """
    Looks up a Server class from the registry by name and instantiates it using the passed parameters.

    Parameters:
        name: The unique identifier of the registered Server.
        kwargs: Parameters required to initialize the Server class.

    Returns:
        An instance of the corresponding Server class.
    """
    server_class = SERVER_REGISTRY.get(server_name)
    
    if server_class is None:
        raise ValueError(f"Server '{server_name}' can not be found in the registry. Please Check `virtual_server/__init__.py`.\n\nAvailable servers:\n{list(SERVER_REGISTRY.keys())}")
        
    try:
        instance = server_class(**kwargs)
        return instance
    except TypeError as e:
        print(f"Error initializing Server '{server_name}'. Please check that the passed parameters are correct.")
        raise e