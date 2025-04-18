"""
API Endpoint for Checkout Tracking

This module provides functionality for tracking user checkout actions
with various retailers and stores.
"""

import logging
from datetime import datetime
from flask import jsonify, request
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

def add_retailer_checkout_endpoint(app):
    """Register the checkout tracking endpoint with the Flask app"""
    
    @app.route('/api/checkout/track', methods=['POST'])
    def track_checkout():
        """Track a user checkout action"""
        # Get JSON data from request
        if not request.json:
            return jsonify({"error": "No JSON data provided"}), 400
            
        # Extract data from request
        data = request.json
        user_id = data.get('user_id')
        store_id = data.get('store_id')
        session_id = data.get('session_id')
        items = data.get('items', [])
        total_amount = data.get('total_amount', 0)
        
        # Validate required fields
        if not store_id:
            return jsonify({"error": "store_id is required"}), 400
            
        if not items:
            return jsonify({"error": "items array is required"}), 400
            
        # Get database connection using the app's connection function
        get_db_connection = app.config.get('get_db_connection')
        if not get_db_connection:
            logger.error("Database connection function not available")
            return jsonify({"error": "Internal server error"}), 500
            
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
            
        try:
            # Record the checkout transaction
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Insert checkout record
            cursor.execute("""
                INSERT INTO checkout_tracking 
                (user_id, store_id, session_id, total_amount, checkout_date)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING checkout_id
            """, (user_id, store_id, session_id, total_amount, datetime.now()))
            
            result = cursor.fetchone()
            checkout_id = result['checkout_id']
            
            # Insert individual items
            for item in items:
                product_id = item.get('product_id')
                product_name = item.get('name', '')
                quantity = item.get('quantity', 1)
                price = item.get('price', 0)
                
                cursor.execute("""
                    INSERT INTO checkout_items
                    (checkout_id, product_id, product_name, quantity, price)
                    VALUES (%s, %s, %s, %s, %s)
                """, (checkout_id, product_id, product_name, quantity, price))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            return jsonify({
                "status": "success",
                "checkout_id": checkout_id,
                "message": "Checkout successfully tracked"
            })
            
        except Exception as e:
            logger.error(f"Error tracking checkout: {str(e)}")
            if conn:
                conn.rollback()
                conn.close()
            return jsonify({"error": str(e)}), 500
    
    # Register the database connection function with the app
    # Make the database connection function available to the route
    from glassrain_unified import get_db_connection
    app.config['get_db_connection'] = get_db_connection