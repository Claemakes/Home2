"""
WSGI Entry point for GlassRain Application

This file is used for production deployment with Gunicorn.
"""

import os
import sys

# Add the parent directory to the Python path to enable imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the Flask app
from glassrain_unified import app

# This variable is used by Gunicorn
application = app

if __name__ == "__main__":
    # If run directly, start the development server
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 3000)), debug=False)