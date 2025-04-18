"""
Error Handling Module for GlassRain

This module provides standardized error handling and logging for the application.
"""

import logging
import traceback
import json
import time
import os
from functools import wraps
from flask import jsonify, request, current_app, g

# Configure logging
logger = logging.getLogger(__name__)

# Error types
class ErrorTypes:
    DATABASE = "DATABASE_ERROR"
    VALIDATION = "VALIDATION_ERROR"
    AUTH = "AUTHENTICATION_ERROR"
    PERMISSION = "PERMISSION_ERROR"
    API = "API_ERROR"
    EXTERNAL = "EXTERNAL_SERVICE_ERROR"
    SERVER = "SERVER_ERROR"
    NOT_FOUND = "NOT_FOUND_ERROR"

# Mapping error types to HTTP status codes
ERROR_STATUS_CODES = {
    ErrorTypes.DATABASE: 500,
    ErrorTypes.VALIDATION: 400,
    ErrorTypes.AUTH: 401,
    ErrorTypes.PERMISSION: 403,
    ErrorTypes.API: 400,
    ErrorTypes.EXTERNAL: 502,
    ErrorTypes.SERVER: 500,
    ErrorTypes.NOT_FOUND: 404
}

class APIError(Exception):
    """Base class for API errors"""
    def __init__(self, message, error_type=ErrorTypes.API, status_code=None, details=None):
        self.message = message
        self.error_type = error_type
        self.status_code = status_code or ERROR_STATUS_CODES.get(error_type, 500)
        self.details = details
        super().__init__(self.message)
    
    def to_dict(self):
        error_dict = {
            "error": True,
            "type": self.error_type,
            "message": self.message
        }
        if self.details:
            error_dict["details"] = self.details
        return error_dict

def handle_error(error):
    """
    Handle errors by logging them and returning a standardized JSON response.
    
    Args:
        error: Exception object
        
    Returns:
        Flask response with error details
    """
    # For API errors (our custom exception)
    if isinstance(error, APIError):
        logger.error(f"API Error ({error.error_type}): {error.message}")
        response = jsonify(error.to_dict())
        response.status_code = error.status_code
        return response
    
    # For other exceptions
    logger.error(f"Unhandled exception: {str(error)}")
    logger.error(traceback.format_exc())
    
    # In development, return full traceback
    if os.environ.get('FLASK_ENV') == 'development':
        details = traceback.format_exc()
    else:
        details = None
    
    response = jsonify({
        "error": True,
        "type": ErrorTypes.SERVER,
        "message": "An unexpected error occurred",
        "details": details
    })
    response.status_code = 500
    return response

def api_error_handler(f):
    """
    Decorator for Flask routes to handle exceptions and return standardized errors.
    
    Args:
        f: Function to decorate
        
    Returns:
        Decorated function
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            # Start timer for performance logging
            start_time = time.time()
            g.request_start_time = start_time
            
            # Execute the route function
            result = f(*args, **kwargs)
            
            # Log performance metrics
            elapsed = time.time() - start_time
            logger.info(f"Request to {request.path} completed in {elapsed:.4f}s")
            
            return result
        except APIError as e:
            return handle_error(e)
        except Exception as e:
            return handle_error(e)
    return decorated_function

def register_error_handlers(app):
    """
    Register error handlers with Flask app.
    
    Args:
        app: Flask application instance
    """
    @app.errorhandler(404)
    def not_found_error(error):
        """Handle 404 errors"""
        logger.warning(f"404 Not Found: {request.path}")
        return jsonify({
            "error": True,
            "type": ErrorTypes.NOT_FOUND,
            "message": f"The requested resource '{request.path}' was not found"
        }), 404
    
    @app.errorhandler(405)
    def method_not_allowed_error(error):
        """Handle 405 Method Not Allowed errors"""
        logger.warning(f"405 Method Not Allowed: {request.method} {request.path}")
        return jsonify({
            "error": True,
            "type": ErrorTypes.API,
            "message": f"Method '{request.method}' not allowed for '{request.path}'"
        }), 405
    
    @app.errorhandler(500)
    def internal_server_error(error):
        """Handle 500 Internal Server Error"""
        logger.error(f"500 Internal Server Error: {str(error)}")
        logger.error(traceback.format_exc())
        
        # In development, return full traceback
        if os.environ.get('FLASK_ENV') == 'development':
            details = traceback.format_exc()
        else:
            details = None
        
        return jsonify({
            "error": True,
            "type": ErrorTypes.SERVER,
            "message": "An unexpected error occurred",
            "details": details
        }), 500
    
    # Add handler for our custom APIError
    @app.errorhandler(APIError)
    def handle_api_error(error):
        return handle_error(error)
    
    # Log each request
    @app.before_request
    def log_request():
        """Log each request before processing"""
        logger.info(f"Request: {request.method} {request.path} from {request.remote_addr}")
        g.request_start_time = time.time()
    
    @app.after_request
    def log_response(response):
        """Log response after request is processed"""
        if hasattr(g, 'request_start_time'):
            elapsed = time.time() - g.request_start_time
            logger.info(f"Response: {response.status_code} in {elapsed:.4f}s")
        return response