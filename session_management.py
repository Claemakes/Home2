"""
Session Management for GlassRain

Handles secure session configuration and middleware for authentication.
"""

import os
import time
import logging
from functools import wraps
from flask import Flask, session, redirect, url_for, request, flash

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Session configuration
SESSION_CONFIG = {
    'secret_key': os.environ.get('FLASK_SECRET_KEY', 'glassrain-dev-secret-key'),
    'permanent': True,
    'lifetime': 3600 * 24 * 7,  # 1 week
    'secure_cookies': False,  # Set to True in production with HTTPS
    'secure_headers': True
}

def configure_session(app):
    """Configure secure session settings for the Flask app"""
    app.secret_key = SESSION_CONFIG['secret_key']
    app.config['SESSION_COOKIE_SECURE'] = SESSION_CONFIG['secure_cookies']
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['PERMANENT_SESSION_LIFETIME'] = SESSION_CONFIG['lifetime']
    app.config['SESSION_REFRESH_EACH_REQUEST'] = True
    
    @app.before_request
    def make_session_permanent():
        session.permanent = SESSION_CONFIG['permanent']
        # Refresh session timer on each request
        session.modified = True
        # Add basic security headers
        if SESSION_CONFIG['secure_headers']:
            session['last_active'] = int(time.time())
    
    logger.info("Session management configured successfully")
    return app

def init_session():
    """Initialize a new session if one doesn't exist"""
    if 'initialized' not in session:
        session['initialized'] = True
        session['last_active'] = int(time.time())
        logger.debug("New session initialized")

def add_security_headers(response):
    """Add security headers to HTTP response"""
    # Content Security Policy
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline' https://api.mapbox.com; style-src 'self' 'unsafe-inline' https://api.mapbox.com; img-src 'self' https://api.mapbox.com data:; connect-src 'self' https://api.mapbox.com https://api.openai.com; frame-src 'self'; object-src 'none';"
    
    # Protection against clickjacking
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    
    # Protection against MIME type confusion attacks
    response.headers['X-Content-Type-Options'] = 'nosniff'
    
    # Protection against reflected XSS
    response.headers['X-XSS-Protection'] = '1; mode=block'
    
    # Referrer policy to control referrer information
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    
    # HTTP Strict Transport Security
    if SESSION_CONFIG['secure_cookies']:
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    
    return response

def login_required(f):
    """Decorator to require login for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to access this page", "warning")
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator to require admin access for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to access this page", "warning")
            return redirect(url_for('login', next=request.url))
        
        if not session.get('is_admin', False):
            flash("Administrator access required", "danger")
            return redirect(url_for('dashboard'))
            
        return f(*args, **kwargs)
    return decorated_function

def get_current_user_id():
    """Get the current logged-in user ID from session"""
    return session.get('user_id')

def get_session_data():
    """Get all non-sensitive session data for debugging"""
    data = {}
    for key, value in session.items():
        # Skip sensitive data
        if key not in ['_csrf_token', 'password', 'user_id']:
            data[key] = value
    return data