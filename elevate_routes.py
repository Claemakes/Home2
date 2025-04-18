"""
Elevate Routes for GlassRain Application

This module provides routes for the Elevate tab functionality including:
- Room scanning
- Room measurements storage and retrieval
- Design saving and management
- AI design assistant interaction
"""

import os
import json
import time
import math
import logging
import psycopg2
from openai import OpenAI
from psycopg2.extras import RealDictCursor
from flask import Blueprint, request, jsonify, render_template
from datetime import datetime

# Initialize OpenAI client
openai_client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY', ''))
logger = logging.getLogger('elevate_routes')
if os.environ.get('OPENAI_API_KEY'):
    logger.info("OpenAI API initialized successfully in elevate_routes")

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('elevate_routes')

elevate_bp = Blueprint('elevate', __name__)

def get_db_connection():
    """Get a connection to the PostgreSQL database"""
    try:
        conn = psycopg2.connect(os.environ.get('DATABASE_URL', ''))
        conn.autocommit = True
        return conn
    except Exception as e:
        logger.error(f"Database connection error: {str(e)}")
        return None

@elevate_bp.route('/elevate')
def elevate_page():
    """Render the Elevate page"""
    address_id = request.args.get('address_id')
    return render_template('elevate.html', address_id=address_id)

@elevate_bp.route('/api/rooms', methods=['GET'])
def get_rooms():
    """Get all scanned rooms for the current user"""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        # Get user ID from session (in production)
        # user_id = session.get('user_id')
        # For demo, we'll use a fixed user ID
        user_id = 1
        
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT id, name, room_type, width, length, height, area, 
                   walls_area, volume, windows, doors, scanned_at, thumbnail_url, model_url
            FROM scanned_rooms
            WHERE user_id = %s
            ORDER BY scanned_at DESC
        """, (user_id,))
        
        rooms = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return jsonify({"rooms": rooms})
    except Exception as e:
        logger.error(f"Error fetching rooms: {str(e)}")
        return jsonify({"error": str(e)}), 500

@elevate_bp.route('/api/rooms', methods=['POST'])
def create_room():
    """Create a new scanned room"""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    if not request.json:
        return jsonify({"error": "No data provided"}), 400
    
    try:
        # Get user ID from session (in production)
        # user_id = session.get('user_id')
        # For demo, we'll use a fixed user ID
        user_id = 1
        
        room_data = request.json
        
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            INSERT INTO scanned_rooms (
                user_id, name, room_type, width, length, height, area,
                walls_area, volume, windows, doors, scanned_at, thumbnail_url, model_url
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            user_id,
            room_data.get('name', 'Unnamed Room'),
            room_data.get('room_type', 'Room'),
            room_data.get('width', 0),
            room_data.get('length', 0),
            room_data.get('height', 0),
            room_data.get('area', 0),
            room_data.get('walls_area', 0),
            room_data.get('volume', 0),
            room_data.get('windows', 0),
            room_data.get('doors', 0),
            datetime.now(),
            room_data.get('thumbnail_url', ''),
            room_data.get('model_url', '')
        ))
        
        result = cursor.fetchone()
        if result is None:
            raise Exception("Failed to insert room record")
        room_id = result['id']
        
        # Save measurements to measurements table if provided
        if 'measurements' in room_data:
            for measurement in room_data['measurements']:
                cursor.execute("""
                    INSERT INTO room_measurements (
                        room_id, measurement_type, value, unit
                    ) VALUES (%s, %s, %s, %s)
                """, (
                    room_id,
                    measurement.get('type', ''),
                    measurement.get('value', 0),
                    measurement.get('unit', '')
                ))
        
        cursor.close()
        conn.close()
        
        return jsonify({"id": room_id, "message": "Room created successfully"})
    except Exception as e:
        logger.error(f"Error creating room: {str(e)}")
        return jsonify({"error": str(e)}), 500

@elevate_bp.route('/api/rooms/<int:room_id>', methods=['DELETE'])
def delete_room(room_id):
    """Delete a scanned room"""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        # Get user ID from session (in production)
        # user_id = session.get('user_id')
        # For demo, we'll use a fixed user ID
        user_id = 1
        
        cursor = conn.cursor()
        
        # First verify the room belongs to the user
        cursor.execute("""
            SELECT id FROM scanned_rooms
            WHERE id = %s AND user_id = %s
        """, (room_id, user_id))
        
        if cursor.fetchone() is None:
            cursor.close()
            conn.close()
            return jsonify({"error": "Room not found or access denied"}), 404
        
        # Delete from room_measurements
        cursor.execute("""
            DELETE FROM room_measurements
            WHERE room_id = %s
        """, (room_id,))
        
        # Delete associated designs
        cursor.execute("""
            DELETE FROM room_designs
            WHERE room_id = %s
        """, (room_id,))
        
        # Delete room
        cursor.execute("""
            DELETE FROM scanned_rooms
            WHERE id = %s
        """, (room_id,))
        
        cursor.close()
        conn.close()
        
        return jsonify({"message": "Room deleted successfully"})
    except Exception as e:
        logger.error(f"Error deleting room: {str(e)}")
        return jsonify({"error": str(e)}), 500

@elevate_bp.route('/api/designs', methods=['GET'])
def get_designs():
    """Get all saved designs for the current user"""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        # Get user ID from session (in production)
        # user_id = session.get('user_id')
        # For demo, we'll use a fixed user ID
        user_id = 1
        
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT d.id, d.name, d.description, d.room_id, r.room_type,
                   d.created_at, d.thumbnail_url, d.tags
            FROM room_designs d
            JOIN scanned_rooms r ON d.room_id = r.id
            WHERE d.user_id = %s
            ORDER BY d.created_at DESC
        """, (user_id,))
        
        designs = cursor.fetchall()
        
        # Convert tags to array if stored as string
        for design in designs:
            if isinstance(design['tags'], str):
                try:
                    design['tags'] = json.loads(design['tags'])
                except:
                    design['tags'] = []
        
        cursor.close()
        conn.close()
        
        return jsonify({"designs": designs})
    except Exception as e:
        logger.error(f"Error fetching designs: {str(e)}")
        return jsonify({"error": str(e)}), 500

@elevate_bp.route('/api/designs', methods=['POST'])
def create_design():
    """Create a new room design"""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    if not request.json:
        return jsonify({"error": "No data provided"}), 400
    
    try:
        # Get user ID from session (in production)
        # user_id = session.get('user_id')
        # For demo, we'll use a fixed user ID
        user_id = 1
        
        design_data = request.json
        
        # Validate required fields
        if 'room_id' not in design_data:
            return jsonify({"error": "room_id is required"}), 400
        
        # Verify the room exists and belongs to the user
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id FROM scanned_rooms
            WHERE id = %s AND user_id = %s
        """, (design_data['room_id'], user_id))
        
        if cursor.fetchone() is None:
            cursor.close()
            conn.close()
            return jsonify({"error": "Room not found or access denied"}), 404
        
        # Prepare tags field
        tags = design_data.get('tags', [])
        if isinstance(tags, list):
            tags_json = json.dumps(tags)
        else:
            tags_json = json.dumps([])
        
        # Store chat history if provided
        chat_history = design_data.get('chat_history', [])
        if isinstance(chat_history, list):
            chat_history_json = json.dumps(chat_history)
        else:
            chat_history_json = json.dumps([])
        
        # Store measurements if provided
        measurements = design_data.get('measurements', {})
        if isinstance(measurements, dict):
            measurements_json = json.dumps(measurements)
        else:
            measurements_json = json.dumps({})
        
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            INSERT INTO room_designs (
                user_id, room_id, name, description, created_at,
                thumbnail_url, chat_history, measurements, tags
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            user_id,
            design_data['room_id'],
            design_data.get('name', 'Unnamed Design'),
            design_data.get('description', ''),
            datetime.now(),
            design_data.get('thumbnail_url', ''),
            chat_history_json,
            measurements_json,
            tags_json
        ))
        
        result = cursor.fetchone()
        if result is None:
            raise Exception("Failed to insert design record")
        design_id = result['id']
        cursor.close()
        conn.close()
        
        return jsonify({"id": design_id, "message": "Design saved successfully"})
    except Exception as e:
        logger.error(f"Error creating design: {str(e)}")
        return jsonify({"error": str(e)}), 500

@elevate_bp.route('/api/designs/<int:design_id>', methods=['DELETE'])
def delete_design(design_id):
    """Delete a room design"""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        # Get user ID from session (in production)
        # user_id = session.get('user_id')
        # For demo, we'll use a fixed user ID
        user_id = 1
        
        cursor = conn.cursor()
        
        # First verify the design belongs to the user
        cursor.execute("""
            SELECT id FROM room_designs
            WHERE id = %s AND user_id = %s
        """, (design_id, user_id))
        
        if cursor.fetchone() is None:
            cursor.close()
            conn.close()
            return jsonify({"error": "Design not found or access denied"}), 404
        
        # Delete design
        cursor.execute("""
            DELETE FROM room_designs
            WHERE id = %s
        """, (design_id,))
        
        cursor.close()
        conn.close()
        
        return jsonify({"message": "Design deleted successfully"})
    except Exception as e:
        logger.error(f"Error deleting design: {str(e)}")
        return jsonify({"error": str(e)}), 500

@elevate_bp.route('/api/design-assistant', methods=['POST'])
def design_assistant():
    """Process a message for the design assistant"""
    if not request.json:
        return jsonify({"error": "No data provided"}), 400
    
    try:
        message_data = request.json
        
        # Verify required fields
        if 'message' not in message_data:
            return jsonify({"error": "message is required"}), 400
        
        # Get user message
        user_message = message_data['message']
        
        # Get room data if provided
        room_data = message_data.get('room', {})
        
        # Get chat history if provided
        chat_history = message_data.get('chat_history', [])
        
        # In a real implementation, this would call the OpenAI API
        # For demo, we'll simulate responses based on keywords
        
        # Simulate processing time
        time.sleep(1)
        
        # Generate a response based on the user message
        response = generate_ai_response(user_message, room_data, chat_history)
        
        return jsonify({
            "response": response,
            "room_updates": {}  # In a real implementation, this would contain updates to apply to the room
        })
    except Exception as e:
        logger.error(f"Error processing design assistant request: {str(e)}")
        return jsonify({"error": str(e)}), 500

def generate_ai_response(message, room, chat_history):
    """
    Generate AI response based on user message using OpenAI API
    """
    import os
    import openai
    import json
    
    # Get OpenAI API key from environment
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        logger.error("OpenAI API key not available")
        return "I'm unable to process your design request at the moment. The design assistant requires an API key to function properly."
    
    try:
        # Get room measurements for context
        width = room.get('width', 12)
        length = room.get('length', 14)
        height = room.get('height', 8)
        area = room.get('area', width * length)
        room_type = room.get('room_type', 'living room')
        
        # Create a formatted room data message
        room_context = f"""Room information:
        - Type: {room_type}
        - Dimensions: {width}' x {length}' (area: {area} sq ft)
        - Ceiling height: {height}'
        - Current features: {', '.join(room.get('features', ['standard walls', 'basic flooring']))}
        """
        
        # Format the chat history
        formatted_history = []
        for chat in chat_history:
            role = "assistant" if chat.get('is_ai', False) else "user"
            formatted_history.append({"role": role, "content": chat.get('message', '')})
        
        # Prepare the messages for the API call
        messages = [
            {"role": "system", "content": "You are an expert interior designer and renovation specialist. Provide detailed, practical advice for home improvement projects. Include cost estimates when appropriate and suggest specific materials, colors, or products. Format suggestions with [suggestion: text] so the interface can display them as clickable options."},
            {"role": "system", "content": room_context}
        ]
        
        # Add chat history if available
        if formatted_history:
            messages.extend(formatted_history)
        
        # Add the current user message
        messages.append({"role": "user", "content": message})
        
        # Make the API call
        response = openai_client.chat.completions.create(
            model="gpt-4o",  # the newest OpenAI model is "gpt-4o" which was released May, 2024
            messages=messages,
            temperature=0.7,
            max_tokens=800
        )
        
        # Extract the response
        return response.choices[0].message.content
        
    except Exception as e:
        logger.error(f"Error generating AI response: {str(e)}")
        return "I apologize, but I encountered an issue processing your design request. Please try again or ask a different question about your room design."

def init_elevate_routes(app):
    """Initialize Elevate routes with the Flask app"""
    app.register_blueprint(elevate_bp)
    
    # Create database tables if they don't exist
    setup_elevate_database()

def setup_elevate_database():
    """Set up database tables for Elevate functionality"""
    conn = get_db_connection()
    if not conn:
        logger.error("Could not connect to database to set up Elevate tables")
        return
    
    try:
        cursor = conn.cursor()
        
        # Create scanned_rooms table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scanned_rooms (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                name VARCHAR(255) NOT NULL,
                room_type VARCHAR(100),
                width FLOAT,
                length FLOAT,
                height FLOAT,
                area FLOAT,
                walls_area FLOAT,
                volume FLOAT,
                windows INTEGER,
                doors INTEGER,
                scanned_at TIMESTAMP,
                thumbnail_url TEXT,
                model_url TEXT
            )
        """)
        
        # Create room_measurements table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS room_measurements (
                id SERIAL PRIMARY KEY,
                room_id INTEGER REFERENCES scanned_rooms(id),
                measurement_type VARCHAR(100),
                value FLOAT,
                unit VARCHAR(20)
            )
        """)
        
        # Create room_designs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS room_designs (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                room_id INTEGER REFERENCES scanned_rooms(id),
                name VARCHAR(255) NOT NULL,
                description TEXT,
                created_at TIMESTAMP,
                thumbnail_url TEXT,
                chat_history JSONB,
                measurements JSONB,
                tags JSONB
            )
        """)
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info("Elevate database tables created successfully")
    except Exception as e:
        logger.error(f"Error setting up Elevate database tables: {str(e)}")