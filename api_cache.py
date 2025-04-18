"""
API Response Caching Module for GlassRain

This module provides caching for API responses to improve performance
by reducing database load for frequently accessed data.
"""

import logging
import json
import time
import hashlib
import functools
from flask import request, current_app

# Configure logging
logger = logging.getLogger(__name__)

# In-memory cache store - for production, use Redis or another distributed cache
_cache = {}

def cache_key(namespace, *args, **kwargs):
    """
    Generate a cache key based on function arguments and request data.
    
    Args:
        namespace: Namespace for the cache key (usually function name)
        *args: Positional arguments
        **kwargs: Keyword arguments
        
    Returns:
        str: Cache key
    """
    # Create a dictionary of all data that affects the cache key
    key_data = {
        'namespace': namespace,
        'args': args,
        'kwargs': kwargs
    }
    
    # If in a Flask request context, add relevant request data
    if request:
        key_data['path'] = request.path
        key_data['query_string'] = request.query_string.decode('utf-8')
        
        # Only include request headers that affect caching
        headers_to_include = ['Accept', 'Accept-Language']
        key_data['headers'] = {k: v for k, v in request.headers.items() 
                              if k in headers_to_include}
    
    # Convert to a JSON string and hash it
    key_str = json.dumps(key_data, sort_keys=True)
    return hashlib.md5(key_str.encode('utf-8')).hexdigest()

def get_cached_data(key):
    """
    Get data from cache if it exists and is not expired.
    
    Args:
        key: Cache key
        
    Returns:
        Cached data or None if not found or expired
    """
    global _cache
    
    cache_entry = _cache.get(key)
    if not cache_entry:
        return None
    
    # Check if entry has expired
    if 'expiry' in cache_entry and cache_entry['expiry'] < time.time():
        # Remove expired entry
        del _cache[key]
        return None
    
    logger.debug(f"Cache hit for key: {key}")
    return cache_entry['data']

def set_cached_data(key, data, ttl=300):
    """
    Store data in cache with expiration time.
    
    Args:
        key: Cache key
        data: Data to cache
        ttl: Time to live in seconds (default: 5 minutes)
    """
    global _cache
    
    # Calculate expiry time
    expiry = time.time() + ttl
    
    _cache[key] = {
        'data': data,
        'expiry': expiry,
        'created_at': time.time()
    }
    logger.debug(f"Cached data with key: {key}, TTL: {ttl}s")

def clear_cache(namespace=None):
    """
    Clear cache entries, optionally filtered by namespace.
    
    Args:
        namespace: Namespace to clear (if None, clear all)
    """
    global _cache
    
    if namespace is None:
        _cache = {}
        logger.info("Cleared entire cache")
    else:
        # Find keys that start with the namespace
        keys_to_delete = [k for k in _cache.keys() if k.startswith(namespace)]
        for key in keys_to_delete:
            del _cache[key]
        logger.info(f"Cleared {len(keys_to_delete)} entries from namespace: {namespace}")

def api_cache(ttl=300, namespace=None):
    """
    Decorator for caching API responses.
    
    Args:
        ttl: Time to live in seconds (default: 5 minutes)
        namespace: Custom namespace (default: function name)
        
    Returns:
        Decorated function
    """
    def decorator(f):
        @functools.wraps(f)
        def decorated_function(*args, **kwargs):
            # Skip caching for non-GET requests
            if request and request.method != 'GET':
                return f(*args, **kwargs)
            
            # Generate cache key
            func_namespace = namespace or f.__name__
            key = cache_key(func_namespace, *args, **kwargs)
            
            # Try to get from cache
            cached_data = get_cached_data(key)
            if cached_data is not None:
                return cached_data
            
            # Execute function and cache the result
            result = f(*args, **kwargs)
            set_cached_data(key, result, ttl)
            return result
        
        return decorated_function
    
    return decorator

# Cache maintenance functions
def init_cache():
    """Initialize the cache system."""
    global _cache
    _cache = {}
    logger.info("Cache system initialized")

def cleanup_expired():
    """Remove expired items from cache."""
    global _cache
    
    now = time.time()
    expired_keys = [k for k, v in _cache.items() 
                   if 'expiry' in v and v['expiry'] < now]
    
    for key in expired_keys:
        del _cache[key]
    
    if expired_keys:
        logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")

def get_cache_stats():
    """
    Get statistics about the cache.
    
    Returns:
        dict: Cache statistics
    """
    global _cache
    
    total_entries = len(_cache)
    now = time.time()
    expired_entries = sum(1 for v in _cache.values() 
                         if 'expiry' in v and v['expiry'] < now)
    
    # Calculate size estimate
    total_size = 0
    for entry in _cache.values():
        if 'data' in entry:
            # Rough size estimation
            data_str = json.dumps(entry['data'])
            total_size += len(data_str)
    
    return {
        'total_entries': total_entries,
        'expired_entries': expired_entries,
        'active_entries': total_entries - expired_entries,
        'total_size_bytes': total_size,
        'total_size_kb': total_size / 1024
    }