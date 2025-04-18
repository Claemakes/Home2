"""
Service Recommendations API Routes for GlassRain

This module provides API endpoints for retrieving service recommendations
for the dashboard and other areas of the application.
"""

from flask import Blueprint, jsonify, request, current_app
import logging
import datetime
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create blueprint
recommendations_bp = Blueprint('recommendations', __name__)

@recommendations_bp.route('/api/service-recommendations', methods=['GET'])
def get_service_recommendations_api():
    """
    API endpoint to get personalized service recommendations
    
    Query parameters:
    - address_id: ID of the property address
    - user_id: ID of the user
    - limit: Maximum number of recommendations to return (default: 3)
    """
    # Extract parameters
    address_id = request.args.get('address_id')
    user_id = request.args.get('user_id')
    limit = request.args.get('limit', 3, type=int)
    
    # Check if the service recommendations module is available
    if not hasattr(current_app, 'service_recs_available') or not current_app.service_recs_available:
        try:
            # Try to import the module
            from service_recommendations import get_service_recommendations, get_upcoming_service_reminders
            current_app.service_recs_available = True
            current_app.get_service_recommendations = get_service_recommendations
            current_app.get_upcoming_service_reminders = get_upcoming_service_reminders
        except ImportError as e:
            logger.error(f"Service recommendations module not available: {str(e)}")
            return jsonify({
                "error": "Service recommendations feature not available",
                "recommendations": []
            }), 500
    
    try:
        # Get recommendations using the imported function
        recommendations = current_app.get_service_recommendations(
            address_id=address_id,
            user_id=user_id,
            limit=limit
        )
        
        # Format response
        response = {
            "count": len(recommendations),
            "recommendations": recommendations
        }
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error getting service recommendations: {str(e)}")
        return jsonify({
            "error": f"Failed to get service recommendations: {str(e)}",
            "recommendations": []
        }), 500

@recommendations_bp.route('/api/service-reminders', methods=['GET'])
def get_service_reminders_api():
    """
    API endpoint to get reminders for upcoming services based on
    recurring schedules and maintenance history
    
    Query parameters:
    - user_id: ID of the user (required)
    - days_ahead: Number of days to look ahead (default: 30)
    """
    # Extract parameters
    user_id = request.args.get('user_id')
    days_ahead = request.args.get('days_ahead', 30, type=int)
    
    # Validate required parameters
    if not user_id:
        return jsonify({"error": "user_id is required"}), 400
    
    # Check if the service recommendations module is available
    if not hasattr(current_app, 'service_recs_available') or not current_app.service_recs_available:
        try:
            # Try to import the module
            from service_recommendations import get_service_recommendations, get_upcoming_service_reminders
            current_app.service_recs_available = True
            current_app.get_service_recommendations = get_service_recommendations
            current_app.get_upcoming_service_reminders = get_upcoming_service_reminders
        except ImportError as e:
            logger.error(f"Service recommendations module not available: {str(e)}")
            return jsonify({
                "error": "Service reminders feature not available",
                "reminders": []
            }), 500
    
    try:
        # Get reminders using the imported function
        reminders = current_app.get_upcoming_service_reminders(
            user_id=user_id,
            days_ahead=days_ahead
        )
        
        # Format response
        response = {
            "count": len(reminders),
            "reminders": reminders
        }
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error getting service reminders: {str(e)}")
        return jsonify({
            "error": f"Failed to get service reminders: {str(e)}",
            "reminders": []
        }), 500

def register_recommendations_routes(app):
    """Register the recommendations blueprint with the Flask app"""
    app.register_blueprint(recommendations_bp)
    logger.info("Service recommendations routes registered")