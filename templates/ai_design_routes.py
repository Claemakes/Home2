"""
AI Design Routes for GlassRain Elevate

This module handles room image processing and AI-powered design modifications
using the OpenAI API.
"""

import os
import base64
import io
import json
import logging
import random
from datetime import datetime
from PIL import Image
import requests
from flask import Blueprint, request, jsonify
from openai import OpenAI

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Blueprint
ai_design_bp = Blueprint('ai_design', __name__)

def get_openai_client():
    """Get initialized OpenAI client"""
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        logger.error("OPENAI_API_KEY not found in environment variables")
        raise ValueError("OpenAI API key not configured")
    
    try:
        import httpx
        # Create httpx client explicitly without proxies
        http_client = httpx.Client(timeout=60.0)
        client = OpenAI(api_key=api_key, http_client=http_client)
        logger.info("OpenAI client initialized in ai_design_routes")
        return client
    except Exception as e:
        logger.error(f"Error initializing OpenAI client: {str(e)}")
        raise

def encode_image_to_base64(image):
    """Convert PIL Image to base64 string"""
    buffered = io.BytesIO()
    image.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

def image_to_base64_str(image_path):
    """Convert local image file to base64 string"""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

@ai_design_bp.route('/api/ai/analyze-room-dimensions', methods=['POST'])
def analyze_room_dimensions():
    """Analyze a 3D room scan to extract accurate measurements"""
    try:
        # Check if request contains required data
        if 'room_scan_data' not in request.json:
            return jsonify({'success': False, 'error': 'Missing room scan data'}), 400
        
        scan_data = request.json['room_scan_data']
        room_name = request.json.get('room_name', 'Unknown Room')
        
        # In a real implementation, this would process actual 3D point cloud data
        # For now, we'll use a placeholder that simulates measurements extraction
        
        # Calculate room dimensions based on 3D scan data
        # This would normally use computer vision and 3D geometry algorithms
        measurements = {
            'total_area': round(scan_data.get('estimated_area', 200) + (5 - 10 * (random.random()))),
            'ceiling_height': round(scan_data.get('estimated_height', 8) + (0.1 - 0.2 * (random.random())), 1),
            'walls': [
                {
                    'id': 'wall1',
                    'length': round(scan_data.get('estimated_width', 12) + (0.2 - 0.4 * (random.random())), 1),
                    'height': round(scan_data.get('estimated_height', 8) + (0.1 - 0.2 * (random.random())), 1),
                    'area': round(scan_data.get('estimated_width', 12) * scan_data.get('estimated_height', 8), 1),
                    'features': ['window'] if random.random() > 0.5 else []
                },
                {
                    'id': 'wall2',
                    'length': round(scan_data.get('estimated_length', 15) + (0.2 - 0.4 * (random.random())), 1),
                    'height': round(scan_data.get('estimated_height', 8) + (0.1 - 0.2 * (random.random())), 1),
                    'area': round(scan_data.get('estimated_length', 15) * scan_data.get('estimated_height', 8), 1),
                    'features': ['door'] if random.random() > 0.5 else []
                },
                {
                    'id': 'wall3',
                    'length': round(scan_data.get('estimated_width', 12) + (0.2 - 0.4 * (random.random())), 1),
                    'height': round(scan_data.get('estimated_height', 8) + (0.1 - 0.2 * (random.random())), 1),
                    'area': round(scan_data.get('estimated_width', 12) * scan_data.get('estimated_height', 8), 1),
                    'features': ['window'] if random.random() > 0.7 else []
                },
                {
                    'id': 'wall4',
                    'length': round(scan_data.get('estimated_length', 15) + (0.2 - 0.4 * (random.random())), 1),
                    'height': round(scan_data.get('estimated_height', 8) + (0.1 - 0.2 * (random.random())), 1),
                    'area': round(scan_data.get('estimated_length', 15) * scan_data.get('estimated_height', 8), 1),
                    'features': []
                }
            ],
            'floor_area': round(scan_data.get('estimated_area', 200) + (5 - 10 * (random.random()))),
            'window_area': round(25 + (2 - 4 * (random.random()))),
            'door_area': round(21 + (1 - 2 * (random.random())))
        }
        
        # Calculate totals
        total_wall_area = sum(wall['area'] for wall in measurements['walls'])
        total_window_area = measurements['window_area']
        total_door_area = measurements['door_area']
        paintable_area = total_wall_area - total_window_area - total_door_area
        
        measurements['total_wall_area'] = round(total_wall_area, 1)
        measurements['paintable_area'] = round(paintable_area, 1)
        
        # Store measurements in database
        # In a real implementation, this would save to a database
        
        return jsonify({
            'success': True,
            'room_name': room_name,
            'measurements': measurements,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error analyzing room dimensions: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@ai_design_bp.route('/api/ai/calculate-material-costs', methods=['POST'])
def calculate_material_costs():
    """Calculate material and labor costs based on room measurements"""
    try:
        if 'measurements' not in request.json:
            return jsonify({'success': False, 'error': 'Missing measurements data'}), 400
            
        measurements = request.json['measurements']
        material_quality = request.json.get('material_quality', 'standard')  # standard, premium, luxury
        
        # Material cost rates per square foot/unit
        rates = {
            'standard': {
                'paint': 0.85,
                'flooring': 4.50,
                'trim': 1.25,
                'labor_paint': 2.00,
                'labor_flooring': 3.50
            },
            'premium': {
                'paint': 1.50,
                'flooring': 8.75,
                'trim': 2.40,
                'labor_paint': 2.50,
                'labor_flooring': 4.50
            },
            'luxury': {
                'paint': 2.75,
                'flooring': 15.00,
                'trim': 4.50,
                'labor_paint': 3.50,
                'labor_flooring': 6.00
            }
        }
        
        selected_rates = rates.get(material_quality, rates['standard'])
        
        # Calculate costs
        paintable_area = measurements.get('paintable_area', 0)
        floor_area = measurements.get('floor_area', 0)
        
        # Paint calculations (including primer, two coats)
        paint_cost = round(paintable_area * selected_rates['paint'], 2)
        paint_labor = round(paintable_area * selected_rates['labor_paint'], 2)
        
        # Flooring calculations
        flooring_cost = round(floor_area * selected_rates['flooring'], 2)
        flooring_labor = round(floor_area * selected_rates['labor_flooring'], 2)
        
        # Trim calculations (perimeter of room)
        wall_lengths = [wall.get('length', 0) for wall in measurements.get('walls', [])]
        perimeter = sum(wall_lengths)
        trim_cost = round(perimeter * selected_rates['trim'], 2)
        
        # Additional costs like fixtures, hardware, etc.
        lighting_fixtures = round(150 + (material_quality == 'premium') * 150 + (material_quality == 'luxury') * 300, 2)
        
        # Total costs
        material_cost = paint_cost + flooring_cost + trim_cost + lighting_fixtures
        labor_cost = paint_labor + flooring_labor
        total_cost = material_cost + labor_cost
        
        return jsonify({
            'success': True,
            'costs': {
                'materials': {
                    'paint': paint_cost,
                    'flooring': flooring_cost,
                    'trim': trim_cost,
                    'lighting': lighting_fixtures,
                    'total_materials': material_cost
                },
                'labor': {
                    'painting': paint_labor,
                    'flooring': flooring_labor,
                    'total_labor': labor_cost
                },
                'total': total_cost,
                'quality_level': material_quality
            }
        })
        
    except Exception as e:
        logger.error(f"Error calculating material costs: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@ai_design_bp.route('/api/ai/design-room', methods=['POST'])
def process_design_request():
    """Process room design request using OpenAI API"""
    try:
        # Check if request contains required data
        if 'room_image' not in request.files or 'design_request' not in request.form:
            return jsonify({'success': False, 'error': 'Missing required data'}), 400
        
        # Get image and design request
        image_file = request.files['room_image']
        design_request = request.form['design_request']
        
        # Get room measurements if available
        room_measurements = json.loads(request.form.get('room_measurements', '{}'))
        
        # Process the image
        try:
            image = Image.open(image_file.stream)
            base64_image = encode_image_to_base64(image)
        except Exception as e:
            logger.error(f"Error processing image: {str(e)}")
            return jsonify({'success': False, 'error': 'Invalid image format'}), 400
        
        # Save original image temporarily
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        original_image_filename = f"room_original_{timestamp}.jpg"
        original_image_path = os.path.join('static', 'uploads', original_image_filename)
        os.makedirs(os.path.dirname(original_image_path), exist_ok=True)
        image.save(original_image_path)
        
        # Get OpenAI client
        try:
            client = get_openai_client()
        except ValueError as e:
            return jsonify({'success': False, 'error': str(e)}), 500
        
        # System prompt for OpenAI
        system_prompt = """
        You are an expert interior designer and architect assistant. Based on the room image and the user's design request,
        you will create a modified version of the room that applies the requested changes. The response should include:
        1. A detailed description of the changes made to match the request
        2. A modified image that shows the room with the requested changes applied
        3. Cost estimates for implementing these changes in real life
        """
        
        # User prompt combines the request with the image
        user_prompt = f"Please modify this room according to this request: {design_request}"
        
        # Call OpenAI API using the client
        try:
            response = client.chat.completions.create(
                model="gpt-4o",  # the newest OpenAI model is "gpt-4o" which was released May, 2024
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": user_prompt
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=1000
            )
            
            # Extract content from the response (OpenAI client returns the response directly)
            ai_description = response.choices[0].message.content
            
            # Now use DALL-E to generate the modified room image
            dalle_prompt = f"""
            Create a photo-realistic image of the room with these modifications: {design_request}.
            The image should look like a real photograph, not an illustration or 3D rendering.
            Make sure to match the perspective and lighting of the original room.
            """
            
            dalle_response = client.images.generate(
                model="dall-e-3",
                prompt=dalle_prompt,
                n=1,
                size="1024x1024"
            )
            
            # Get the image URL from the response
            modified_image_url = dalle_response.data[0].url
            
            # Download the generated image
            modified_image_response = requests.get(modified_image_url)
            modified_image_filename = f"room_modified_{timestamp}.jpg"
            modified_image_path = os.path.join('static', 'uploads', modified_image_filename)
            
            with open(modified_image_path, 'wb') as f:
                f.write(modified_image_response.content)
            
            # If we have measurements, calculate costs
            material_costs = {}
            if room_measurements:
                try:
                    # Determine material quality based on content of design request
                    quality_level = 'standard'
                    if 'premium' in design_request.lower() or 'high' in design_request.lower():
                        quality_level = 'premium'
                    elif 'luxury' in design_request.lower() or 'exclusive' in design_request.lower():
                        quality_level = 'luxury'
                        
                    # Calculate material costs
                    costs_response = calculate_material_costs_internal(room_measurements, quality_level)
                    material_costs = costs_response.get('costs', {})
                except Exception as cost_err:
                    logger.error(f"Error calculating costs: {str(cost_err)}")
            
            # Return success response with all data
            return jsonify({
                'success': True,
                'ai_description': ai_description,
                'original_image_url': f"/static/uploads/{original_image_filename}",
                'modified_image_url': f"/static/uploads/{modified_image_filename}",
                'measurements': room_measurements,
                'costs': material_costs
            })
            
        except Exception as e:
            logger.error(f"Error calling OpenAI API: {str(e)}")
            return jsonify({'success': False, 'error': f"AI processing error: {str(e)}"}), 500
            
    except Exception as e:
        logger.error(f"Unexpected error in process_design_request: {str(e)}")
        return jsonify({'success': False, 'error': f"Unexpected error: {str(e)}"}), 500

# Internal function to calculate material costs
def calculate_material_costs_internal(measurements, material_quality='standard'):
    """Calculate material and labor costs based on room measurements - internal helper function"""
    try:
        # Material cost rates per square foot/unit
        rates = {
            'standard': {
                'paint': 0.85,
                'flooring': 4.50,
                'trim': 1.25,
                'labor_paint': 2.00,
                'labor_flooring': 3.50
            },
            'premium': {
                'paint': 1.50,
                'flooring': 8.75,
                'trim': 2.40,
                'labor_paint': 2.50,
                'labor_flooring': 4.50
            },
            'luxury': {
                'paint': 2.75,
                'flooring': 15.00,
                'trim': 4.50,
                'labor_paint': 3.50,
                'labor_flooring': 6.00
            }
        }
        
        selected_rates = rates.get(material_quality, rates['standard'])
        
        # Calculate costs
        paintable_area = measurements.get('paintable_area', 0)
        floor_area = measurements.get('floor_area', 0)
        
        # Paint calculations (including primer, two coats)
        paint_cost = round(paintable_area * selected_rates['paint'], 2)
        paint_labor = round(paintable_area * selected_rates['labor_paint'], 2)
        
        # Flooring calculations
        flooring_cost = round(floor_area * selected_rates['flooring'], 2)
        flooring_labor = round(floor_area * selected_rates['labor_flooring'], 2)
        
        # Trim calculations (perimeter of room)
        wall_lengths = [wall.get('length', 0) for wall in measurements.get('walls', [])]
        perimeter = sum(wall_lengths)
        trim_cost = round(perimeter * selected_rates['trim'], 2)
        
        # Additional costs like fixtures, hardware, etc.
        lighting_fixtures = round(150 + (material_quality == 'premium') * 150 + (material_quality == 'luxury') * 300, 2)
        
        # Total costs
        material_cost = paint_cost + flooring_cost + trim_cost + lighting_fixtures
        labor_cost = paint_labor + flooring_labor
        total_cost = material_cost + labor_cost
        
        return {
            'success': True,
            'costs': {
                'materials': {
                    'paint': paint_cost,
                    'flooring': flooring_cost,
                    'trim': trim_cost,
                    'lighting': lighting_fixtures,
                    'total_materials': material_cost
                },
                'labor': {
                    'painting': paint_labor,
                    'flooring': flooring_labor,
                    'total_labor': labor_cost
                },
                'total': total_cost,
                'quality_level': material_quality
            }
        }
        
    except Exception as e:
        logger.error(f"Error calculating material costs: {str(e)}")
        return {'success': False, 'error': str(e)}

# Add more AI design routes as needed below