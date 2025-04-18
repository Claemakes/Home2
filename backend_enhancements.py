"""
Backend Enhancements Integration Module for GlassRain

This module integrates all backend enhancement modules into the main Flask application.
"""

import logging
import sys
import os
from flask import Flask

# Add the current directory to the path to ensure imports work correctly
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import enhancement modules
from glassrain_production.db_pool import init_pool
from glassrain_production.error_handler import register_error_handlers
from glassrain_production.rate_limiter import setup_rate_limiting
from glassrain_production.api_cache import init_cache
from glassrain_production.task_processor import init_executor, init_task_routes
from glassrain_production.db_setup_enhancements import setup_enhanced_database
from glassrain_production.async_data_processor import register_async_data_routes
from glassrain_production.data_validation import run_comprehensive_validation

# Configure logging
logger = logging.getLogger(__name__)

def init_backend_enhancements(app):
    """
    Initialize all backend enhancements for the Flask application.
    
    Args:
        app: Flask application instance
        
    Returns:
        bool: True if all enhancements were initialized successfully
    """
    try:
        # Initialize database connection pool
        logger.info("Initializing database connection pool...")
        pool_initialized = init_pool(min_conn=2, max_conn=10)
        
        if not pool_initialized:
            logger.warning("Failed to initialize database connection pool")
            return False
        
        # Setup enhanced database tables
        logger.info("Setting up enhanced database tables...")
        db_setup_success = setup_enhanced_database()
        
        if not db_setup_success:
            logger.warning("Failed to setup enhanced database tables")
            # Continue anyway, as some features may still work
        
        # Initialize error handlers
        logger.info("Registering error handlers...")
        register_error_handlers(app)
        
        # Initialize rate limiting
        logger.info("Setting up rate limiting...")
        setup_rate_limiting(app)
        
        # Initialize API caching
        logger.info("Initializing API cache...")
        init_cache()
        
        # Initialize background task processor
        logger.info("Initializing background task processor...")
        init_executor(app)
        init_task_routes(app)
        
        # Register async data processing routes
        logger.info("Registering async data processing routes...")
        register_async_data_routes(app)
        
        # Register validation endpoint
        logger.info("Registering system validation endpoint...")
        register_validation_endpoint(app)
        
        logger.info("✅ All backend enhancements initialized successfully")
        return True
    
    except Exception as e:
        logger.error(f"❌ Error initializing backend enhancements: {str(e)}")
        return False

def register_validation_endpoint(app):
    """
    Register a system validation endpoint with the Flask app.
    
    Args:
        app: Flask application instance
    """
    from flask import jsonify, request, send_file
    from glassrain_production.data_validation import run_comprehensive_validation, export_validation_report
    
    @app.route('/api/system/validate', methods=['GET'])
    def api_validate_system():
        """API endpoint to run system validation"""
        try:
            format_type = request.args.get('format', 'json')
            if format_type not in ['json', 'html']:
                format_type = 'json'
                
            # Run comprehensive validation
            validation_results = run_comprehensive_validation()
            
            # Export validation report
            report_path = export_validation_report(validation_results, format=format_type)
            
            # Return file or JSON data
            if request.args.get('download', 'false').lower() == 'true':
                return send_file(report_path, as_attachment=True)
            else:
                return jsonify({
                    "success": True,
                    "all_valid": validation_results["all_valid"],
                    "issues_count": len(validation_results.get("issues_summary", [])),
                    "validation_time_seconds": validation_results.get("validation_time_seconds"),
                    "report_path": report_path
                })
        
        except Exception as e:
            logger.error(f"Error in system validation API: {str(e)}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
    
    logger.info("System validation endpoint registered at /api/system/validate")