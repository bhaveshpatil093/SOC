import functools
from cachetools import TTLCache
import hashlib
import json

# Global cache: max 100 items, expires in 300 seconds (5 mins)
_api_cache = TTLCache(maxsize=100, ttl=300)

def cache_response():
    """
    A decorator to cache FastAPI responses based on query string parameters.
    Only caches if the response is JSON serializable.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Extract request object
            request = kwargs.get("request")
            if not request:
                return func(*args, **kwargs)
                
            # Create a cache key based on the function name and query params
            query_str = request.url.query
            key_str = f"{func.__name__}:{query_str}"
            cache_key = hashlib.md5(key_str.encode()).hexdigest()
            
            if cache_key in _api_cache:
                return _api_cache[cache_key]
                
            # Execute function
            response = func(*args, **kwargs)
            
            # Cache response
            _api_cache[cache_key] = response
            return response
        return wrapper
    return decorator
