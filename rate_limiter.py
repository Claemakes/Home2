"""
Enhanced Rate Limiting Module for GlassRain

This module provides improved rate limiting for API endpoints to prevent abuse.
"""

import logging
import time
import threading
from functools import wraps
from flask import request, jsonify, current_app, g
from collections import defaultdict

# Configure logging
logger = logging.getLogger(__name__)

class RateLimiter:
    """
    Enhanced rate limiter class that provides token bucket implementation
    for more refined rate limiting.
    """
    
    def __init__(self):
        """Initialize the rate limiter."""
        # Store client's request counts
        self.request_records = defaultdict(list)
        
        # Token bucket implementation
        self.token_buckets = {}
        
        # Thread lock for thread safety
        self.lock = threading.Lock()
        
        # Cache of rate limit decisions to avoid recalculation
        self.decision_cache = {}
        
        # Cleanup expired records periodically
        self.cleanup_thread = threading.Thread(target=self._cleanup_expired_records, daemon=True)
        self.cleanup_thread.start()
    
    def _get_client_identifier(self, request):
        """
        Get a unique identifier for the client.
        
        Args:
            request: Flask request object
            
        Returns:
            str: Client identifier (IP address by default)
        """
        # Use X-Forwarded-For header if available (for running behind proxies)
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            client_ip = forwarded_for.split(',')[0].strip()
        else:
            client_ip = request.remote_addr
        
        # Add more factors for identification if needed
        # For example, you could add request.user if authentication is implemented
        return client_ip
    
    def is_rate_limited(self, request, limit=15, window=60):
        """
        Check if a request should be rate limited.
        This implements a sliding window approach.
        
        Args:
            request: Flask request object
            limit: Maximum number of requests allowed in the window
            window: Time window in seconds
            
        Returns:
            tuple: (is_limited, remaining, reset_time)
        """
        with self.lock:
            # Get client identifier
            client_id = self._get_client_identifier(request)
            
            # Check cache to see if we already made a decision for this client
            cache_key = f"{client_id}:{limit}:{window}"
            cached_decision = self.decision_cache.get(cache_key)
            
            if cached_decision:
                # If decision was made recently, use cached result
                if time.time() - cached_decision['time'] < 1:  # Cache for 1 second
                    return cached_decision['is_limited'], cached_decision['remaining'], cached_decision['reset']
            
            # Get current time
            now = time.time()
            
            # Filter out requests outside the window
            self.request_records[client_id] = [
                t for t in self.request_records[client_id] if now - t < window
            ]
            
            # Count recent requests
            recent_requests = len(self.request_records[client_id])
            
            # Check if rate limit exceeded
            is_limited = recent_requests >= limit
            
            # Calculate remaining requests and reset time
            remaining = max(0, limit - recent_requests)
            
            # Calculate when the rate limit will reset
            if recent_requests > 0:
                oldest_request = min(self.request_records[client_id])
                reset_time = oldest_request + window
            else:
                reset_time = now + window
            
            # If not rate limited, add current request
            if not is_limited:
                self.request_records[client_id].append(now)
            
            # Cache the decision
            self.decision_cache[cache_key] = {
                'is_limited': is_limited,
                'remaining': remaining,
                'reset': reset_time,
                'time': now
            }
            
            return is_limited, remaining, reset_time
    
    def _cleanup_expired_records(self):
        """Periodically clean up expired rate limit records."""
        while True:
            try:
                time.sleep(60)  # Run cleanup every minute
                
                with self.lock:
                    now = time.time()
                    
                    # Clear expired request records (older than 1 hour)
                    for client_id in list(self.request_records.keys()):
                        self.request_records[client_id] = [
                            t for t in self.request_records[client_id] if now - t < 3600
                        ]
                        
                        # Remove empty client records
                        if not self.request_records[client_id]:
                            del self.request_records[client_id]
                    
                    # Clear expired decision cache
                    for key in list(self.decision_cache.keys()):
                        if now - self.decision_cache[key]['time'] > 60:
                            del self.decision_cache[key]
                    
                    # Log cleanup results
                    logger.debug(f"Rate limiter cleanup: {len(self.request_records)} clients tracked")
            
            except Exception as e:
                logger.error(f"Error in rate limiter cleanup: {str(e)}")

# Create a global rate limiter instance
rate_limiter = RateLimiter()

def rate_limit(limit=15, window=60, key_func=None):
    """
    Decorator for rate limiting Flask routes.
    
    Args:
        limit: Maximum number of requests allowed in the window
        window: Time window in seconds
        key_func: Optional function to generate a custom rate limit key
        
    Returns:
        Decorated function
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Check rate limit
            is_limited, remaining, reset_time = rate_limiter.is_rate_limited(
                request, limit, window
            )
            
            # Set rate limit headers
            resp_headers = {
                'X-RateLimit-Limit': str(limit),
                'X-RateLimit-Remaining': str(remaining),
                'X-RateLimit-Reset': str(int(reset_time))
            }
            
            # Store headers in Flask g object for the after_request handler
            g.rate_limit_headers = resp_headers
            
            # If rate limited, return 429 response
            if is_limited:
                logger.warning(f"Rate limit exceeded for {request.remote_addr}: {request.path}")
                response = jsonify({
                    "error": "Rate limit exceeded",
                    "message": f"Too many requests. Try again in {int(reset_time - time.time())} seconds"
                })
                response.status_code = 429
                for key, value in resp_headers.items():
                    response.headers[key] = value
                
                # Additional Retry-After header as per HTTP spec
                response.headers['Retry-After'] = str(int(reset_time - time.time()))
                
                return response
            
            # Execute the route function
            return f(*args, **kwargs)
        
        return decorated_function
    
    return decorator

def setup_rate_limiting(app):
    """
    Setup rate limiting for a Flask app.
    
    Args:
        app: Flask application instance
    """
    @app.after_request
    def add_rate_limit_headers(response):
        """Add rate limit headers to all responses."""
        if hasattr(g, 'rate_limit_headers'):
            for key, value in g.rate_limit_headers.items():
                response.headers[key] = value
        return response
    
    # Register a route to check rate limit status
    @app.route('/api/rate-limit-status')
    def rate_limit_status():
        """API endpoint to check current rate limit status."""
        _, remaining, reset_time = rate_limiter.is_rate_limited(request)
        return jsonify({
            "rate_limit": {
                "remaining": remaining,
                "reset": int(reset_time),
                "reset_in_seconds": int(reset_time - time.time())
            }
        })
    
    logger.info("Rate limiting system initialized")