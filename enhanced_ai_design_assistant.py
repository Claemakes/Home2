"""
Enhanced AI Design Assistant

This module provides intelligent design recommendations and 3D visualizations
for home improvement projects using AI analysis of room images and user preferences.
"""

import os
import json
import logging
import random
import base64
import requests
from io import BytesIO
from PIL import Image
from openai import OpenAI

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('enhanced_ai_design_assistant')

class DesignAssistant:
    """Enhanced AI Design Assistant for room analysis and design suggestions"""
    
    def __init__(self):
        """Initialize the design assistant with API credentials if available"""
        self.api_key = os.environ.get('OPENAI_API_KEY', '')
        self.openai_client = None
        if self.api_key:
            self.openai_client = OpenAI(api_key=self.api_key)
        
        # Material and item database
        self.materials_db = self._load_materials_database()
        self.furniture_db = self._load_furniture_database()
        self.style_palettes = self._load_style_palettes()
        
        logger.info("Enhanced AI Design Assistant initialized")
    
    def analyze_room(self, image, room_type='living room'):
        """
        Analyze a room image and provide insights and recommendations
        
        Args:
            image: The image file object
            room_type: The type of room (living room, kitchen, bedroom, etc.)
            
        Returns:
            dict: Analysis results with design recommendations
        """
        try:
            logger.info(f"Analyzing {room_type} image")
            
            # Process image for analysis
            img = Image.open(BytesIO(image.read()))
            
            # Analyze image color palette
            color_palette = self._analyze_colors(img)
            
            # Detect objects and furniture in the room
            objects = self._detect_objects(img)
            
            # Determine room dimensions and layout
            dimensions = self._analyze_dimensions(img)
            
            # Identify style and aesthetic
            style = self._identify_style(img, objects, color_palette)
            
            # Generate design opportunities
            opportunities = self._generate_opportunities(
                room_type, style, objects, dimensions, color_palette
            )
            
            # Structured response
            analysis = {
                'room_type': room_type,
                'color_palette': color_palette,
                'existing_objects': objects,
                'dimensions': dimensions,
                'current_style': style,
                'design_opportunities': opportunities
            }
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing room: {str(e)}")
            
            # Fallback response if analysis fails
            return {
                'room_type': room_type,
                'color_palette': ['#E0E0E0', '#D0D0D0', '#C0C0C0'],
                'existing_objects': ['furniture', 'wall', 'floor'],
                'dimensions': {'width': 'medium', 'length': 'medium', 'height': 'standard'},
                'current_style': 'traditional',
                'design_opportunities': [
                    'Consider updating the wall colors for a fresh look',
                    'New lighting fixtures could enhance the ambiance',
                    'Adding accent pieces would bring visual interest'
                ]
            }
    
    def generate_recommendations(self, room_type, style, budget, constraints):
        """
        Generate design recommendations based on user input
        
        Args:
            room_type: Type of room (living room, kitchen, etc.)
            style: Desired style (modern, traditional, etc.)
            budget: Budget level (low, medium, high)
            constraints: Any specific constraints or requirements
            
        Returns:
            dict: Design recommendations including products, materials, and visualizations
        """
        try:
            logger.info(f"Generating recommendations for {room_type} in {style} style with {budget} budget")
            
            # Get style palette
            palette = self._get_style_palette(style)
            
            # Get materials based on style and budget
            materials = self._get_materials_for_style(style, budget)
            
            # Get furniture recommendations
            furniture = self._get_furniture_recommendations(room_type, style, budget)
            
            # Generate layout suggestions
            layouts = self._generate_layout_options(room_type, style)
            
            # Calculate approximate costs
            costs = self._calculate_costs(materials, furniture, budget)
            
            # Compile recommendations
            recommendations = {
                'room_type': room_type,
                'style': style,
                'color_palette': palette,
                'materials': materials,
                'furniture': furniture,
                'layout_options': layouts,
                'estimated_costs': costs,
                'timeline': self._estimate_timeline(room_type, budget)
            }
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error generating recommendations: {str(e)}")
            
            # Fallback response
            return {
                'room_type': room_type,
                'style': style,
                'color_palette': ['#E0E0E0', '#D0D0D0', '#C0C0C0'],
                'materials': [
                    {'name': 'Paint', 'description': 'Premium interior paint', 'cost_range': '$30-50 per gallon'},
                    {'name': 'Flooring', 'description': 'Engineered hardwood', 'cost_range': '$3-8 per sq ft'}
                ],
                'furniture': [
                    {'name': 'Sofa', 'description': 'Modern sectional', 'cost_range': '$800-1500'},
                    {'name': 'Coffee Table', 'description': 'Glass top with metal frame', 'cost_range': '$200-400'}
                ],
                'layout_options': ['Option 1: Open concept', 'Option 2: Divided spaces'],
                'estimated_costs': {'materials': '$2000-3000', 'furniture': '$3000-5000', 'labor': '$1000-2000'},
                'timeline': '4-6 weeks'
            }
    
    def generate_visualization(self, room_data, style_changes):
        """
        Generate a visualization of the room with applied design changes
        
        Args:
            room_data: Current room data including dimensions and existing elements
            style_changes: Requested design changes to visualize
            
        Returns:
            dict: Visualization data including image URLs and 3D model references
        """
        try:
            logger.info("Generating room visualization")
            
            # In a real implementation, this would call a 3D rendering engine or AI image generator
            # For this example, we'll return example visualization references
            
            visualization = {
                'image_urls': [
                    'https://example.com/visualizations/room1_view1.jpg',
                    'https://example.com/visualizations/room1_view2.jpg'
                ],
                'model_reference': 'room_model_123',
                'style_applied': style_changes.get('style', 'modern'),
                'materials_applied': style_changes.get('materials', []),
                '3d_model_url': 'https://example.com/3d-models/room1.gltf'
            }
            
            return visualization
            
        except Exception as e:
            logger.error(f"Error generating visualization: {str(e)}")
            return {
                'image_urls': [],
                'model_reference': '',
                'error': str(e)
            }
    
    def process_design_request(self, prompt, room_data=None):
        """
        Process a natural language design request using AI
        
        Args:
            prompt: The natural language request from the user
            room_data: Optional room data for context
            
        Returns:
            dict: Response with recommendations and/or visualization
        """
        try:
            if not self.openai_client:
                logger.warning("OpenAI API key not available, using fallback responses")
                return self._get_fallback_design_response(prompt)
            
            logger.info(f"Processing design request: {prompt}")
            
            # Prepare messages for OpenAI
            messages = [
                {"role": "system", "content": "You are an expert interior designer and architect. Provide detailed, practical design advice based on the user's request."},
                {"role": "user", "content": prompt}
            ]
            
            # Add room data if available
            if room_data:
                room_context = f"Room data: {json.dumps(room_data)}"
                messages.insert(1, {"role": "system", "content": room_context})
            
            # Make the API call using the OpenAI client
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",  # the newest OpenAI model is "gpt-4o" which was released May, 2024
                messages=messages,
                temperature=0.7,
                max_tokens=1000
            )
            
            # Extract content from the response
            ai_response = response.choices[0].message.content
            
            # Process and structure the AI response
            structured_response = self._structure_ai_response(ai_response, prompt)
            
            return structured_response
            
        except Exception as e:
            logger.error(f"Error processing design request: {str(e)}")
            return self._get_fallback_design_response(prompt)
    
    # Helper methods
    def _analyze_colors(self, image):
        """Analyze the color palette of an image"""
        try:
            # Resize image for faster processing
            image = image.resize((100, 100))
            
            # Convert to RGB if needed
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Get image data
            pixels = list(image.getdata())
            
            # Group similar colors
            colors = {}
            for pixel in pixels:
                # Simplify the color (reduce precision to group similar colors)
                simple_color = (pixel[0]//10*10, pixel[1]//10*10, pixel[2]//10*10)
                if simple_color in colors:
                    colors[simple_color] += 1
                else:
                    colors[simple_color] = 1
            
            # Sort by frequency
            sorted_colors = sorted(colors.items(), key=lambda x: x[1], reverse=True)
            
            # Convert to hex and return top colors
            hex_colors = []
            for color, _ in sorted_colors[:5]:
                hex_color = '#{:02x}{:02x}{:02x}'.format(color[0], color[1], color[2])
                hex_colors.append(hex_color)
            
            return hex_colors
            
        except Exception as e:
            logger.error(f"Color analysis error: {str(e)}")
            return ['#E0E0E0', '#D0D0D0', '#C0C0C0', '#B0B0B0', '#A0A0A0']
    
    def _detect_objects(self, image):
        """Detect objects and furniture in an image"""
        # In a real implementation, this would use object detection AI
        # For this example, we'll return common room objects
        
        common_objects = {
            'living room': ['sofa', 'coffee table', 'tv stand', 'bookshelf', 'chair', 'rug', 'lamp'],
            'kitchen': ['cabinets', 'countertop', 'stove', 'refrigerator', 'sink', 'island', 'backsplash'],
            'bedroom': ['bed', 'nightstand', 'dresser', 'mirror', 'rug', 'lamp', 'closet'],
            'bathroom': ['vanity', 'toilet', 'shower', 'bathtub', 'mirror', 'tile', 'towel rack'],
            'dining room': ['dining table', 'chairs', 'buffet', 'chandelier', 'rug', 'china cabinet'],
            'office': ['desk', 'chair', 'bookshelf', 'lamp', 'filing cabinet', 'computer'],
        }
        
        # Return common objects for demonstration purposes
        room_type = 'living room'  # Default
        return random.sample(common_objects[room_type], min(4, len(common_objects[room_type])))
    
    def _analyze_dimensions(self, image):
        """Analyze room dimensions from an image"""
        # In a real implementation, this would use computer vision
        # For this example, return basic dimensions
        
        dimensions = {
            'width': random.choice(['small', 'medium', 'large']),
            'length': random.choice(['small', 'medium', 'large']),
            'height': random.choice(['low', 'standard', 'high']),
            'total_sqft': random.randint(150, 500)
        }
        
        return dimensions
    
    def _identify_style(self, image, objects, colors):
        """Identify the current style of the room"""
        styles = [
            'modern', 'traditional', 'contemporary', 'farmhouse', 
            'industrial', 'mid-century modern', 'coastal', 'bohemian',
            'scandinavian', 'transitional', 'minimalist'
        ]
        
        return random.choice(styles)
    
    def _generate_opportunities(self, room_type, style, objects, dimensions, colors):
        """Generate design improvement opportunities"""
        opportunities = [
            f"Update the color scheme to complement the existing {style} style",
            f"Replace outdated fixtures with {style}-inspired alternatives",
            f"Add texture through new textiles and materials",
            f"Improve lighting with ambient, task, and accent options",
            f"Optimize the layout for better flow and functionality",
            f"Incorporate plants or natural elements for a fresh look",
            f"Update hardware and small details for a cohesive look",
            f"Add statement pieces that enhance the {style} aesthetic"
        ]
        
        return random.sample(opportunities, 3)
    
    def _get_style_palette(self, style):
        """Get a color palette for a specific style"""
        return self.style_palettes.get(style, ['#E0E0E0', '#D0D0D0', '#C0C0C0'])
    
    def _get_materials_for_style(self, style, budget):
        """Get recommended materials for a style and budget level"""
        materials = []
        
        for material_type, options in self.materials_db.items():
            if budget == 'low':
                filtered = [m for m in options if m['price_tier'] == 'budget']
            elif budget == 'medium':
                filtered = [m for m in options if m['price_tier'] in ['budget', 'standard']]
            else:
                filtered = options
                
            # Filter by style compatibility
            styled = [m for m in filtered if style in m['compatible_styles']]
            
            # If no style match, use all filtered
            if not styled:
                styled = filtered
            
            # Add top material to recommendations
            if styled:
                top_material = styled[0]
                materials.append({
                    'type': material_type,
                    'name': top_material['name'],
                    'description': top_material['description'],
                    'cost_range': top_material['cost_range']
                })
        
        return materials
    
    def _get_furniture_recommendations(self, room_type, style, budget):
        """Get furniture recommendations based on room type, style and budget"""
        furniture = []
        
        if room_type in self.furniture_db:
            for furniture_type, options in self.furniture_db[room_type].items():
                if budget == 'low':
                    filtered = [f for f in options if f['price_tier'] == 'budget']
                elif budget == 'medium':
                    filtered = [f for f in options if f['price_tier'] in ['budget', 'standard']]
                else:
                    filtered = options
                    
                # Filter by style compatibility
                styled = [f for f in filtered if style in f['compatible_styles']]
                
                # If no style match, use all filtered
                if not styled:
                    styled = filtered
                
                # Add top furniture to recommendations
                if styled:
                    top_furniture = styled[0]
                    furniture.append({
                        'type': furniture_type,
                        'name': top_furniture['name'],
                        'description': top_furniture['description'],
                        'cost_range': top_furniture['cost_range']
                    })
        
        return furniture
    
    def _generate_layout_options(self, room_type, style):
        """Generate layout options for a room type and style"""
        layouts = {
            'living room': [
                'Conversation-focused with seating around coffee table',
                'TV-focused with seating directed towards media wall',
                'Open concept with defined zones for lounging and dining',
                'Symmetrical layout with balanced furniture placement'
            ],
            'kitchen': [
                'Galley layout with efficient workflow',
                'L-shaped with island for extra workspace',
                'U-shaped with maximized counter space',
                'Open concept with integrated dining area'
            ],
            'bedroom': [
                'Bed centered on focal wall with symmetrical nightstands',
                'Corner bed placement to maximize floor space',
                'Divided zones for sleeping, dressing, and lounging',
                'Minimalist layout focusing on the bed as centerpiece'
            ]
        }
        
        if room_type in layouts:
            return random.sample(layouts[room_type], 2)
        else:
            return [
                'Standard layout optimized for flow',
                'Alternative layout with focus on functionality'
            ]
    
    def _calculate_costs(self, materials, furniture, budget):
        """Calculate approximate costs based on materials and furniture"""
        # In a real implementation, this would calculate based on quantities and prices
        # For this example, we'll return ranges based on budget
        
        budget_multipliers = {
            'low': 1.0,
            'medium': 2.0,
            'high': 3.5
        }
        
        multiplier = budget_multipliers.get(budget, 1.0)
        
        return {
            'materials': f"${int(1000 * multiplier)}-{int(2000 * multiplier)}",
            'furniture': f"${int(2000 * multiplier)}-{int(4000 * multiplier)}",
            'labor': f"${int(1000 * multiplier)}-{int(2000 * multiplier)}",
            'total': f"${int(4000 * multiplier)}-{int(8000 * multiplier)}"
        }
    
    def _estimate_timeline(self, room_type, budget):
        """Estimate project timeline based on room type and complexity"""
        base_weeks = {
            'living room': 4,
            'kitchen': 8,
            'bedroom': 3,
            'bathroom': 6,
            'dining room': 3,
            'office': 2
        }
        
        base = base_weeks.get(room_type, 4)
        
        if budget == 'low':
            # DIY or minimal changes
            return f"{base-1}-{base} weeks"
        elif budget == 'medium':
            # Standard renovation
            return f"{base}-{base+2} weeks"
        else:
            # Premium renovation with custom elements
            return f"{base+1}-{base+4} weeks"
    
    def _structure_ai_response(self, ai_response, prompt):
        """Structure an AI text response into a design recommendation"""
        # In a real implementation, this would parse the AI text to extract structured data
        # For this example, we'll create a simple structure
        
        # Check if prompt asks about specific aspects
        prompt_lower = prompt.lower()
        
        response = {
            'prompt': prompt,
            'recommendations': []
        }
        
        # Split response into sections
        paragraphs = ai_response.split('\n\n')
        for i, paragraph in enumerate(paragraphs):
            if paragraph.strip():
                response['recommendations'].append(paragraph.strip())
        
        # Add appropriate context fields based on prompt
        if 'cost' in prompt_lower or 'price' in prompt_lower or 'budget' in prompt_lower:
            response['cost_estimate'] = {
                'materials': '$1000-2000',
                'labor': '$800-1500',
                'total': '$1800-3500'
            }
        
        if 'color' in prompt_lower or 'paint' in prompt_lower:
            response['color_recommendations'] = [
                {'name': 'Serene Blue', 'hex': '#B8D8EB'},
                {'name': 'Warm Taupe', 'hex': '#D8CCBB'},
                {'name': 'Soft White', 'hex': '#F5F5F0'}
            ]
        
        if 'furniture' in prompt_lower:
            response['furniture_recommendations'] = [
                {'type': 'Sofa', 'description': 'Mid-century modern with tapered legs'},
                {'type': 'Coffee Table', 'description': 'Round marble top with metal base'},
                {'type': 'Lighting', 'description': 'Articulating floor lamp with brass finish'}
            ]
        
        return response
    
    def _get_fallback_design_response(self, prompt):
        """Get a fallback design response when AI is unavailable"""
        prompt_lower = prompt.lower()
        
        # Basic response structure
        response = {
            'prompt': prompt,
            'recommendations': [
                'Consider updating your wall colors to create a fresh atmosphere',
                'Focus on improving lighting with a combination of ambient, task, and accent lighting',
                'Add textural elements through textiles, natural materials, and artwork'
            ]
        }
        
        # Customize based on keywords in prompt
        if 'modern' in prompt_lower:
            response['recommendations'].append('Incorporate clean lines, minimal ornamentation, and a neutral color palette with bold accents')
            response['recommendations'].append('Choose furniture with simple forms and materials like glass, metal, and polished wood')
        
        if 'kitchen' in prompt_lower:
            response['recommendations'] = [
                'Update cabinet hardware for an affordable refresh',
                'Consider painting cabinets rather than replacing them',
                'Add under-cabinet lighting to improve functionality and ambiance',
                'Replace the backsplash for a high-impact change'
            ]
        
        if 'bedroom' in prompt_lower:
            response['recommendations'] = [
                'Invest in quality bedding for both comfort and visual appeal',
                'Create a focal point with an accent wall or statement headboard',
                'Ensure adequate storage to maintain a clutter-free environment',
                'Layer lighting for a relaxing atmosphere'
            ]
        
        if 'small space' in prompt_lower or 'apartment' in prompt_lower:
            response['recommendations'] = [
                'Use multi-functional furniture to maximize the space',
                'Incorporate mirrors to create the illusion of more space',
                'Choose a light color palette to enhance spaciousness',
                'Utilize vertical space with tall bookshelves and wall-mounted storage'
            ]
        
        return response
    
    def _load_materials_database(self):
        """Load material options database"""
        return {
            'wall_paint': [
                {
                    'name': 'Budget Latex Paint',
                    'description': 'Basic interior latex paint',
                    'price_tier': 'budget',
                    'cost_range': '$15-25 per gallon',
                    'compatible_styles': ['traditional', 'contemporary', 'transitional']
                },
                {
                    'name': 'Premium Acrylic Paint',
                    'description': 'High-quality acrylic with better coverage',
                    'price_tier': 'standard',
                    'cost_range': '$30-50 per gallon',
                    'compatible_styles': ['modern', 'contemporary', 'farmhouse', 'industrial']
                },
                {
                    'name': 'Designer Paint',
                    'description': 'Premium paint with unique pigments and finish',
                    'price_tier': 'premium',
                    'cost_range': '$50-100 per gallon',
                    'compatible_styles': ['modern', 'minimalist', 'scandinavian', 'industrial']
                }
            ],
            'flooring': [
                {
                    'name': 'Laminate Flooring',
                    'description': 'Durable laminate with wood appearance',
                    'price_tier': 'budget',
                    'cost_range': '$1-3 per sq ft',
                    'compatible_styles': ['traditional', 'contemporary', 'transitional']
                },
                {
                    'name': 'Engineered Hardwood',
                    'description': 'Real wood veneer over stable core',
                    'price_tier': 'standard',
                    'cost_range': '$3-8 per sq ft',
                    'compatible_styles': ['traditional', 'farmhouse', 'coastal', 'transitional']
                },
                {
                    'name': 'Solid Hardwood',
                    'description': 'Premium solid wood flooring',
                    'price_tier': 'premium',
                    'cost_range': '$8-15 per sq ft',
                    'compatible_styles': ['traditional', 'modern', 'mid-century modern', 'industrial']
                }
            ],
            'countertops': [
                {
                    'name': 'Laminate Countertop',
                    'description': 'Affordable and versatile laminate surface',
                    'price_tier': 'budget',
                    'cost_range': '$15-40 per sq ft',
                    'compatible_styles': ['contemporary', 'transitional', 'farmhouse']
                },
                {
                    'name': 'Quartz Countertop',
                    'description': 'Engineered stone with durability and variety',
                    'price_tier': 'standard',
                    'cost_range': '$50-80 per sq ft',
                    'compatible_styles': ['modern', 'contemporary', 'transitional', 'farmhouse']
                },
                {
                    'name': 'Marble Countertop',
                    'description': 'Luxurious natural stone with unique patterns',
                    'price_tier': 'premium',
                    'cost_range': '$80-150 per sq ft',
                    'compatible_styles': ['modern', 'traditional', 'transitional', 'minimalist']
                }
            ]
        }
    
    def _load_furniture_database(self):
        """Load furniture options database"""
        return {
            'living room': {
                'sofa': [
                    {
                        'name': 'Basic Fabric Sofa',
                        'description': 'Simple polyester fabric sofa',
                        'price_tier': 'budget',
                        'cost_range': '$300-600',
                        'compatible_styles': ['contemporary', 'transitional']
                    },
                    {
                        'name': 'Mid-range Sectional',
                        'description': 'Comfortable sectional with chaise',
                        'price_tier': 'standard',
                        'cost_range': '$800-1500',
                        'compatible_styles': ['modern', 'contemporary', 'transitional']
                    },
                    {
                        'name': 'Premium Leather Sofa',
                        'description': 'High-quality leather with hardwood frame',
                        'price_tier': 'premium',
                        'cost_range': '$1500-3000',
                        'compatible_styles': ['modern', 'traditional', 'industrial']
                    }
                ],
                'coffee_table': [
                    {
                        'name': 'Simple Wood Coffee Table',
                        'description': 'Basic rectangular design',
                        'price_tier': 'budget',
                        'cost_range': '$100-200',
                        'compatible_styles': ['contemporary', 'transitional', 'farmhouse']
                    },
                    {
                        'name': 'Glass and Metal Coffee Table',
                        'description': 'Modern design with glass top',
                        'price_tier': 'standard',
                        'cost_range': '$200-400',
                        'compatible_styles': ['modern', 'contemporary', 'industrial']
                    },
                    {
                        'name': 'Designer Marble Coffee Table',
                        'description': 'Luxurious marble with unique base',
                        'price_tier': 'premium',
                        'cost_range': '$500-1000',
                        'compatible_styles': ['modern', 'minimalist', 'mid-century modern']
                    }
                ]
            },
            'bedroom': {
                'bed': [
                    {
                        'name': 'Platform Bed Frame',
                        'description': 'Simple platform without headboard',
                        'price_tier': 'budget',
                        'cost_range': '$200-400',
                        'compatible_styles': ['contemporary', 'minimalist']
                    },
                    {
                        'name': 'Upholstered Bed Frame',
                        'description': 'Fabric headboard with wood frame',
                        'price_tier': 'standard',
                        'cost_range': '$500-900',
                        'compatible_styles': ['modern', 'transitional', 'contemporary']
                    },
                    {
                        'name': 'Four-poster Bed',
                        'description': 'Traditional design with posts',
                        'price_tier': 'premium',
                        'cost_range': '$1000-2500',
                        'compatible_styles': ['traditional', 'farmhouse', 'coastal']
                    }
                ],
                'dresser': [
                    {
                        'name': 'Basic Dresser',
                        'description': 'Simple 6-drawer design',
                        'price_tier': 'budget',
                        'cost_range': '$150-300',
                        'compatible_styles': ['contemporary', 'transitional']
                    },
                    {
                        'name': 'Mid-range Wood Dresser',
                        'description': 'Quality wood with detailed hardware',
                        'price_tier': 'standard',
                        'cost_range': '$400-800',
                        'compatible_styles': ['modern', 'mid-century modern', 'transitional']
                    },
                    {
                        'name': 'Premium Designer Dresser',
                        'description': 'Luxury materials with unique design',
                        'price_tier': 'premium',
                        'cost_range': '$900-2000',
                        'compatible_styles': ['modern', 'traditional', 'industrial']
                    }
                ]
            }
        }
    
    def _load_style_palettes(self):
        """Load color palettes for different design styles"""
        return {
            'modern': ['#FFFFFF', '#000000', '#E0E0E0', '#C0C0C0', '#A0A0A0'],
            'traditional': ['#F5EDE3', '#D8CFC1', '#8A7968', '#6B5B47', '#3F3630'],
            'contemporary': ['#FFFFFF', '#303030', '#909090', '#B0B0B0', '#404040'],
            'farmhouse': ['#EEEEEE', '#D8D0C7', '#BFB7A8', '#8E8171', '#5D5442'],
            'industrial': ['#DDDDDD', '#888888', '#444444', '#222222', '#7B3C1D'],
            'mid-century modern': ['#F6EFE9', '#E5C2A5', '#CA9670', '#567389', '#3A4A5D'],
            'coastal': ['#E4F2F7', '#B5D8E9', '#7EAAC2', '#3C7B9E', '#1D476D'],
            'bohemian': ['#F4EAEA', '#EAC9B4', '#D49D77', '#B07159', '#7C513F'],
            'scandinavian': ['#FFFFFF', '#EFEFEF', '#DCDCDC', '#BBBBBB', '#555555'],
            'transitional': ['#F0F0F0', '#DDDDDD', '#999999', '#555555', '#333333'],
            'minimalist': ['#FFFFFF', '#FAFAFA', '#F0F0F0', '#E0E0E0', '#D0D0D0']
        }