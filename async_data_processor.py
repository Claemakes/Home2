"""
Asynchronous Data Processing Module for GlassRain

This module provides background processing for data-intensive operations
such as property analysis, service recommendations, and contractor matching.
"""

import logging
import time
import json
import os
import traceback
from datetime import datetime, timedelta
import sys

# Ensure correct paths for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from glassrain_production.task_processor import background_task, task_progress
from glassrain_production.db_pool import execute_query, execute_modify

# Configure logging
logger = logging.getLogger(__name__)

@background_task(name="property_analysis", description="Analyze property data and extract insights")
def analyze_property(address_id, user_id=None):
    """
    Analyze property data in the background and store insights.
    
    Args:
        address_id: ID of the address to analyze
        user_id: Optional user ID for filtering
        
    Returns:
        dict: Analysis results
    """
    logger.info(f"Starting property analysis for address_id={address_id}")
    
    # Update progress to 10%
    task_progress(analyze_property.current_task.task_id, 10, "Starting property analysis")
    
    try:
        # Get address details
        address_query = """
            SELECT * FROM addresses WHERE id = %s
        """
        address_data = execute_query(address_query, (address_id,))
        
        if not address_data or len(address_data) == 0:
            raise ValueError(f"Address not found: {address_id}")
        
        address = address_data[0]
        full_address = f"{address['street']}, {address['city']}, {address['state']} {address['zip']}"
        
        # Update progress to 20%
        task_progress(analyze_property.current_task.task_id, 20, 
                     f"Retrieved address information for {full_address}")
        
        # Simulate property analysis (in a real implementation, this would call ML models, etc.)
        time.sleep(2)  # Simulating time-intensive analysis
        
        # Update progress to 50%
        task_progress(analyze_property.current_task.task_id, 50, "Processing property characteristics")
        
        # Generate property insights
        insights = {
            "address_id": address_id,
            "full_address": full_address,
            "analysis_date": datetime.now().isoformat(),
            "property_insights": {
                "estimated_size": "2,400 sq ft",  # This would be calculated in a real implementation
                "estimated_age": "27 years",
                "construction_type": "Wood frame",
                "roof_type": "Asphalt shingle",
                "estimated_value": "$320,000"
            },
            "maintenance_insights": {
                "roof_replacement_recommended": "Within 3-5 years",
                "exterior_painting_recommended": "Within 1-2 years",
                "hvac_service_recommended": "Immediate",
                "window_efficiency": "Moderate, consider updating"
            }
        }
        
        # Update progress to 80%
        task_progress(analyze_property.current_task.task_id, 80, "Generating recommendations")
        
        # Store insights in database
        store_query = """
            INSERT INTO property_insights 
            (address_id, analysis_date, insights_data, user_id) 
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (address_id) 
            DO UPDATE SET 
                analysis_date = EXCLUDED.analysis_date,
                insights_data = EXCLUDED.insights_data
            RETURNING id
        """
        
        result = execute_query(
            store_query, 
            (
                address_id, 
                datetime.now(), 
                json.dumps(insights), 
                user_id
            )
        )
        
        if not result:
            logger.warning(f"Failed to store property insights for address_id={address_id}")
        
        # Update progress to 100%
        task_progress(analyze_property.current_task.task_id, 100, "Analysis complete")
        
        return insights
        
    except Exception as e:
        logger.error(f"Error in property analysis: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Update progress with error
        task_progress(analyze_property.current_task.task_id, 0, f"Error: {str(e)}")
        
        raise e

@background_task(name="seasonal_service_check", description="Check for seasonal services due")
def check_seasonal_services():
    """
    Check for seasonal services that are due for all registered properties.
    
    Returns:
        dict: Summary of services due
    """
    logger.info("Starting seasonal services check")
    
    try:
        # Update progress to 10%
        task_progress(check_seasonal_services.current_task.task_id, 10, "Starting seasonal service check")
        
        # Get current date information
        now = datetime.now()
        current_month = now.month
        
        # Update progress to 20%
        task_progress(check_seasonal_services.current_task.task_id, 20, "Analyzing seasonal patterns")
        
        # Query for seasonal services
        seasonal_query = """
            SELECT s.*, c.name as category_name
            FROM services s
            JOIN service_categories c ON s.category_id = c.id
            WHERE s.is_seasonal = TRUE
        """
        seasonal_services = execute_query(seasonal_query)
        
        if not seasonal_services:
            return {"error": "No seasonal services found"}
        
        # Update progress to 40%
        task_progress(check_seasonal_services.current_task.task_id, 40, 
                     f"Found {len(seasonal_services)} seasonal services")
        
        # Filter services by current season
        current_season_services = []
        
        for service in seasonal_services:
            start_month = service.get('start_month')
            end_month = service.get('end_month')
            
            # If start_month is None, use a default value of 1
            if start_month is None:
                start_month = 1
                
            # If end_month is None, use a default value of 12
            if end_month is None:
                end_month = 12
                
            # Check if current month is within service season
            if start_month <= end_month:
                # Normal season (e.g., Apr-Aug)
                if start_month <= current_month <= end_month:
                    current_season_services.append(service)
            else:
                # Season spans year boundary (e.g., Nov-Feb)
                if current_month >= start_month or current_month <= end_month:
                    current_season_services.append(service)
        
        # Update progress to 60%
        task_progress(check_seasonal_services.current_task.task_id, 60, 
                     f"Filtered to {len(current_season_services)} current season services")
        
        # Get all addresses
        addresses_query = "SELECT * FROM addresses"
        addresses = execute_query(addresses_query)
        
        if not addresses:
            return {"error": "No addresses found"}
        
        # Update progress to 80%
        task_progress(check_seasonal_services.current_task.task_id, 80, 
                     f"Checking {len(addresses)} properties for seasonal services")
        
        # Build recommendations for each address
        recommendations = []
        
        for address in addresses:
            address_services = []
            
            for service in current_season_services:
                # In a real implementation, we would check service history to see if this 
                # service was already performed recently
                address_services.append({
                    "service_id": service['id'],
                    "service_name": service['name'],
                    "category_name": service['category_name'],
                    "description": service['description'],
                    "is_urgent": service.get('is_urgent', False),
                    "recommended_date": (now + timedelta(days=14)).isoformat()
                })
            
            if address_services:
                recommendations.append({
                    "address_id": address['id'],
                    "address": f"{address['street']}, {address['city']}, {address['state']} {address['zip']}",
                    "services_due": address_services
                })
        
        # Update progress to 100%
        task_progress(check_seasonal_services.current_task.task_id, 100, "Seasonal service check complete")
        
        # Return summary
        summary = {
            "seasonal_check_date": now.isoformat(),
            "total_addresses": len(addresses),
            "total_seasonal_services": len(seasonal_services),
            "current_season_services": len(current_season_services),
            "addresses_with_recommendations": len(recommendations),
            "recommendations": recommendations
        }
        
        return summary
        
    except Exception as e:
        logger.error(f"Error in seasonal services check: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Update progress with error
        task_progress(check_seasonal_services.current_task.task_id, 0, f"Error: {str(e)}")
        
        raise e

def register_async_data_routes(app):
    """
    Register routes for async data processing with the Flask app.
    
    Args:
        app: Flask application instance
    """
    from flask import request, jsonify
    
    @app.route('/api/async/analyze-property', methods=['POST'])
    def api_analyze_property():
        """API endpoint to start property analysis"""
        if not request.json:
            return jsonify({"error": "No JSON data provided"}), 400
        
        address_id = request.json.get('address_id')
        user_id = request.json.get('user_id')
        
        if not address_id:
            return jsonify({"error": "address_id is required"}), 400
        
        # Submit the background task
        task = analyze_property.submit(address_id, user_id)
        
        return jsonify({
            "success": True,
            "task_id": task.task_id,
            "status": task.status,
            "message": f"Property analysis for address {address_id} started"
        })
    
    @app.route('/api/async/check-seasonal-services', methods=['POST'])
    def api_check_seasonal_services():
        """API endpoint to start seasonal services check"""
        # Submit the background task
        task = check_seasonal_services.submit()
        
        return jsonify({
            "success": True,
            "task_id": task.task_id,
            "status": task.status,
            "message": "Seasonal services check started"
        })
    
    logger.info("Async data processing routes registered")