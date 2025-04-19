"""
WSGI Entry point for GlassRain Application

This file is used for production deployment with Gunicorn.
"""

import os
import sys

# Add the current directory to the Python path to enable imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Add any additional paths needed for modules
templates_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
sys.path.insert(0, templates_path)

try:
    # First try to import from root directory
    from glassrain_unified import app
except ImportError:
    try:
        # If that fails, try to import from templates directory
        from templates.glassrain_unified import app
    except ImportError as e:
        # If both fail, print error for debugging
        import logging
        logging.error(f"Error importing Flask app: {e}")
        logging.error(f"Python path: {sys.path}")
        logging.error(f"Files in current directory: {os.listdir('.')}")
        logging.error(f"Files in templates directory: {os.listdir('templates') if os.path.exists('templates') else 'templates directory not found'}")
        raise

# Patch Flask app template folder if needed
if hasattr(app, 'template_folder') and app.template_folder == 'templates':
    # If app is trying to use a templates subfolder but is already in templates folder
    # then update it to use the current directory
    app.template_folder = '.'

# This variable is used by Gunicorn
application = app

if __name__ == "__main__":
    # If run directly, start the development server
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 3000)), debug=False)
