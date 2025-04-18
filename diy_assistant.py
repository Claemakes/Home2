"""
DIY Assistant Module

This module provides AI-powered DIY home improvement assistance,
including project recommendations, step-by-step guides, and
expert answers to home improvement questions.
"""

import os
import re
import json
import logging
import random
import requests
from typing import List, Dict, Any, Optional
from datetime import datetime
from openai import OpenAI

# Configure logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('diy_assistant')

class DIYAssistant:
    """DIY Assistant for home improvement projects and advice"""
    
    def __init__(self, api_key=None):
        """
        Initialize the DIY Assistant
        
        Args:
            api_key (str, optional): OpenAI API key for AI assistance
        """
        self.api_key = api_key or os.environ.get('OPENAI_API_KEY', '')
        self.openai_client = None
        if self.api_key:
            self.openai_client = OpenAI(api_key=self.api_key)
        
        # Load project database
        self.projects_db = self._load_projects_database()
        self.categories = self._extract_categories()
        self.difficulty_levels = ['easy', 'medium', 'advanced', 'expert']
        
        logger.info("DIY Assistant initialized")
    
    def get_projects(self, difficulty=None, category=None, search=None) -> List[Dict[str, Any]]:
        """
        Get DIY projects filtered by difficulty, category, and/or search term
        
        Args:
            difficulty (str, optional): Filter by difficulty level
            category (str, optional): Filter by category
            search (str, optional): Search term to filter projects
            
        Returns:
            list: List of matching projects
        """
        logger.info(f"Getting projects with filters - difficulty: {difficulty}, category: {category}, search: {search}")
        
        try:
            filtered_projects = self.projects_db.copy()
            
            # Filter by difficulty
            if difficulty and difficulty.lower() in self.difficulty_levels:
                filtered_projects = [p for p in filtered_projects if p.get('difficulty', '').lower() == difficulty.lower()]
            
            # Filter by category
            if category:
                filtered_projects = [p for p in filtered_projects if category.lower() in p.get('category', '').lower()]
            
            # Filter by search term
            if search:
                search_terms = search.lower().split()
                filtered_projects = [
                    p for p in filtered_projects 
                    if any(
                        term in p.get('title', '').lower() or 
                        term in p.get('description', '').lower() or
                        term in p.get('category', '').lower() or
                        any(term in tag.lower() for tag in p.get('tags', []))
                        for term in search_terms
                    )
                ]
            
            # Sort by popularity (if available) or alphabetically
            filtered_projects.sort(key=lambda x: (-(x.get('popularity', 0)), x.get('title', '')))
            
            return filtered_projects[:20]  # Limit to 20 results
            
        except Exception as e:
            logger.error(f"Error getting projects: {str(e)}")
            return []
    
    def get_project_details(self, project_id: str) -> Dict:
        """
        Get detailed information about a specific project
        
        Args:
            project_id (str): ID of the project
            
        Returns:
            dict: Project details
        """
        try:
            # Find project by ID
            for project in self.projects_db:
                if project.get('id') == project_id:
                    return project
            
            return {}
            
        except Exception as e:
            logger.error(f"Error getting project details: {str(e)}")
            return {}
    
    def ask_question(self, question: str) -> str:
        """
        Get an AI-generated answer to a DIY question
        
        Args:
            question (str): The DIY question
            
        Returns:
            str: The answer to the question
        """
        if not question:
            return "Please ask a home improvement or DIY question."
        
        logger.info(f"Answering DIY question: {question}")
        
        try:
            if not self.openai_client:
                logger.warning("OpenAI API key not available, using fallback responses")
                return self._get_fallback_response(question)
            
            # Use the OpenAI client for API call
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",  # the newest OpenAI model is "gpt-4o" which was released May, 2024
                messages=[
                    {
                        "role": "system", 
                        "content": """You are a knowledgeable home improvement and DIY expert. 
                                    Provide clear, accurate, and helpful advice about home repairs, renovations,
                                    and DIY projects. Include specific steps, tool recommendations, safety precautions,
                                    and approximate costs when relevant. Keep responses concise but thorough."""
                    },
                    {
                        "role": "user", 
                        "content": question
                    }
                ],
                temperature=0.7,
                max_tokens=800
            )
            
            # Extract content from the response
            answer = response.choices[0].message.content.strip()
            
            return answer
            
        except Exception as e:
            logger.error(f"Error answering question: {str(e)}")
            return self._get_fallback_response(question)
    
    def analyze_image(self, image_data, question=None):
        """
        Analyze an image of a DIY project or home issue
        
        Args:
            image_data: Image data
            question (str, optional): Question about the image
            
        Returns:
            dict: Analysis results
        """
        try:
            if not self.openai_client:
                logger.warning("OpenAI API key not available, using fallback responses")
                return {
                    "analysis": "Unable to analyze image without API key.",
                    "recommendations": [
                        "Consider basic maintenance like filling cracks or holes",
                        "Check for water damage signs if this is a concerning area",
                        "Consult with a professional for structural issues"
                    ]
                }
            
            # In a real implementation, this would use OpenAI's Vision API or similar
            # For now, return a fallback response
            analysis = "I can see what appears to be a home improvement project or issue."
            
            if question:
                analysis += f" Regarding your question: '{question}', "
                
                if "leak" in question.lower() or "water" in question.lower():
                    analysis += "I can see signs of water damage that may indicate a leak. "
                elif "paint" in question.lower():
                    analysis += "the surface appears to need proper preparation before painting. "
                elif "crack" in question.lower():
                    analysis += "there are visible cracks that should be addressed. "
                
            recommendations = [
                "Clean the area thoroughly before making any repairs",
                "Consider using a primer before applying paint or other finishes",
                "For best results, use proper tools and materials specific to this project"
            ]
            
            return {
                "analysis": analysis,
                "recommendations": recommendations
            }
            
        except Exception as e:
            logger.error(f"Error analyzing image: {str(e)}")
            return {
                "analysis": "Unable to analyze the image due to an error.",
                "recommendations": [
                    "Consider consulting with a professional",
                    "Ensure the area is safe before attempting DIY repairs"
                ]
            }
    
    def get_material_estimate(self, project_type, room_size):
        """
        Estimate materials needed for a DIY project
        
        Args:
            project_type (str): Type of project (e.g., 'painting', 'flooring')
            room_size (dict): Dimensions of the room
            
        Returns:
            dict: Material estimates
        """
        try:
            area = room_size.get('length', 10) * room_size.get('width', 10)
            
            if project_type.lower() == 'painting':
                # Typical paint coverage is ~400 sq ft per gallon
                paint_gallons = round(area / 350, 1)  # Slightly less for safety
                primer_gallons = round(area / 400, 1)
                
                return {
                    'materials': [
                        {
                            'name': 'Interior Paint',
                            'quantity': f"{paint_gallons} gallons",
                            'estimated_cost': f"${int(paint_gallons * 35)}-${int(paint_gallons * 50)}"
                        },
                        {
                            'name': 'Primer',
                            'quantity': f"{primer_gallons} gallons",
                            'estimated_cost': f"${int(primer_gallons * 25)}-${int(primer_gallons * 35)}"
                        },
                        {
                            'name': 'Paint Rollers',
                            'quantity': '2-3',
                            'estimated_cost': "$15-25"
                        },
                        {
                            'name': 'Paint Brushes (various sizes)',
                            'quantity': '3-5',
                            'estimated_cost': "$20-40"
                        },
                        {
                            'name': 'Drop Cloths',
                            'quantity': '2-3',
                            'estimated_cost': "$15-30"
                        },
                        {
                            'name': 'Painter\'s Tape',
                            'quantity': '2-3 rolls',
                            'estimated_cost': "$15-25"
                        }
                    ],
                    'total_estimated_cost': f"${int((paint_gallons * 42.5) + (primer_gallons * 30) + 80)}-${int((paint_gallons * 50) + (primer_gallons * 35) + 120)}"
                }
                
            elif project_type.lower() == 'flooring':
                # Add 10% for waste
                flooring_area = area * 1.1
                
                # Laminate flooring typically comes in 20-25 sq ft boxes
                boxes = round(flooring_area / 22, 0)
                
                return {
                    'materials': [
                        {
                            'name': 'Laminate Flooring',
                            'quantity': f"{boxes} boxes (~{int(boxes * 22)} sq ft)",
                            'estimated_cost': f"${int(boxes * 35)}-${int(boxes * 60)}"
                        },
                        {
                            'name': 'Underlayment',
                            'quantity': f"{int(area)} sq ft",
                            'estimated_cost': f"${int(area * 0.3)}-${int(area * 0.5)}"
                        },
                        {
                            'name': 'Transition Strips',
                            'quantity': f"{int(room_size.get('width', 10) * 0.5)} pieces",
                            'estimated_cost': f"${int(room_size.get('width', 10) * 10)}-${int(room_size.get('width', 10) * 15)}"
                        },
                        {
                            'name': 'Vapor Barrier',
                            'quantity': f"{int(area)} sq ft",
                            'estimated_cost': f"${int(area * 0.2)}-${int(area * 0.3)}"
                        }
                    ],
                    'total_estimated_cost': f"${int((boxes * 47.5) + (area * 0.4) + (room_size.get('width', 10) * 12.5) + (area * 0.25))}-${int((boxes * 60) + (area * 0.5) + (room_size.get('width', 10) * 15) + (area * 0.3))}"
                }
                
            else:
                return {
                    'materials': [
                        {
                            'name': 'Various materials',
                            'quantity': 'Depends on project specifics',
                            'estimated_cost': "Please provide more details for an accurate estimate"
                        }
                    ],
                    'total_estimated_cost': "Varies based on specific requirements"
                }
                
        except Exception as e:
            logger.error(f"Error estimating materials: {str(e)}")
            return {
                'materials': [
                    {
                        'name': 'Various materials',
                        'quantity': 'Estimate unavailable',
                        'estimated_cost': 'Unable to calculate'
                    }
                ],
                'total_estimated_cost': 'Unable to calculate'
            }
    
    def _extract_categories(self) -> List[str]:
        """Extract unique categories from the projects database"""
        categories = set()
        for project in self.projects_db:
            if 'category' in project and project['category']:
                categories.add(project['category'])
        return sorted(list(categories))
    
    def _get_fallback_response(self, question: str) -> str:
        """Generate a fallback response when the API is unavailable"""
        question_lower = question.lower()
        
        # Check for common DIY questions and provide canned responses
        if any(word in question_lower for word in ['paint', 'painting']):
            return """For painting projects, follow these steps:
1. Prepare the surface by cleaning and sanding
2. Apply primer (especially important for new drywall or when changing colors significantly)
3. Use quality brushes and rollers appropriate for your surface
4. Apply 2 coats of paint, allowing proper drying time between coats
5. For best results, use painter's tape for clean edges

For a typical room, you'll need 1-2 gallons of paint depending on the size and wall condition. 
Quality paint typically costs $30-50 per gallon. Don't forget supplies like drop cloths, tape, rollers, and brushes."""
            
        elif any(word in question_lower for word in ['plumb', 'leak', 'pipe', 'toilet', 'faucet']):
            return """For minor plumbing issues:
1. Always turn off the water supply before beginning work
2. Use Teflon tape on threaded connections to prevent leaks
3. Have a bucket and towels ready for any residual water
4. For fixture replacement, take photos before disassembly as a reference
5. If you encounter any major leaks or complications, don't hesitate to call a professional

Basic plumbing tools like an adjustable wrench, pliers, and pipe tape are essential. For more complex jobs involving pipe replacement or moving fixtures, professional help is recommended."""
            
        elif any(word in question_lower for word in ['floor', 'tile', 'laminate']):
            return """For flooring installation:
1. Ensure your subfloor is clean, dry, and level
2. Allow flooring materials to acclimate to your home for 48-72 hours
3. Use appropriate underlayment for your flooring type
4. Leave expansion gaps around the perimeter
5. Work in small sections and check your alignment frequently

For tools, you'll need a saw appropriate for your flooring type, a measuring tape, spacers, and tapping block. Most flooring projects cost $2-10 per square foot in materials depending on quality."""
            
        elif any(word in question_lower for word in ['electric', 'wiring', 'outlet']):
            return """For electrical work, safety is paramount:
1. ALWAYS turn off power at the breaker panel before beginning work
2. Use a voltage tester to confirm power is off
3. Follow local electrical codes
4. For anything beyond simple fixture or switch replacement, consider hiring a licensed electrician

Electrical work can be dangerous and often requires permits. Simple projects like replacing outlets can be DIY-friendly with proper precautions, but rewiring or panel work should be left to professionals."""
            
        else:
            return """For most home improvement projects, here are general tips:

1. Plan thoroughly before starting - measure twice, cut once
2. Gather all necessary tools and materials before beginning
3. Allow more time than you think you'll need
4. Follow manufacturer instructions for any products you use
5. Start with smaller projects to build skills and confidence
6. YouTube tutorials can be helpful for visual learners
7. Don't hesitate to consult a professional for complex or potentially dangerous work

For more specific advice about your project, please provide details about what you're working on."""
    
    def _load_projects_database(self) -> List[Dict[str, Any]]:
        """Load the DIY projects database"""
        # In a real implementation, this would load from a database
        # For now, return a sample set of projects
        return [
            {
                "id": "p001",
                "title": "Refresh Your Walls with Paint",
                "description": "Transform your space with a fresh coat of paint. This beginner-friendly project can dramatically change the look and feel of any room.",
                "difficulty": "easy",
                "category": "Interior",
                "time_estimate": "1-2 days",
                "cost_estimate": "$100-300",
                "popularity": 95,
                "tags": ["painting", "walls", "interior", "decor"],
                "materials": [
                    "Interior paint (1-2 gallons per room)",
                    "Primer (if needed)",
                    "Paint rollers and frames",
                    "Paint brushes (various sizes)",
                    "Paint tray",
                    "Painter's tape",
                    "Drop cloths",
                    "Sandpaper",
                    "Spackling paste (for holes)",
                    "Putty knife"
                ],
                "tools": [
                    "Ladder or step stool",
                    "Screwdriver (for outlet covers)",
                    "Sanding block"
                ],
                "steps": [
                    "Remove furniture or move to center of room",
                    "Remove switch plates and outlet covers",
                    "Clean walls thoroughly",
                    "Repair holes with spackling and sand smooth",
                    "Apply painter's tape around trim and fixtures",
                    "Apply primer if needed (new drywall or major color change)",
                    "Paint ceiling first, then walls",
                    "Apply 2 coats, allowing proper drying time",
                    "Remove tape while paint is still slightly wet",
                    "Replace outlet covers and furniture"
                ],
                "image_url": "/static/diy/painting.jpg",
                "tips": [
                    "Choose high-quality paint for better coverage and durability",
                    "Sample colors on your wall before committing",
                    "Paint in natural daylight for best color accuracy",
                    "Cut in edges first, then roll larger areas"
                ],
                "safety": [
                    "Ensure good ventilation",
                    "Use a sturdy ladder",
                    "Take breaks to avoid fatigue"
                ]
            },
            {
                "id": "p002",
                "title": "Install Luxury Vinyl Plank Flooring",
                "description": "Replace worn carpet or outdated flooring with modern luxury vinyl planks. Durable, waterproof, and available in many styles.",
                "difficulty": "medium",
                "category": "Flooring",
                "time_estimate": "1-3 days",
                "cost_estimate": "$2-7 per sq ft",
                "popularity": 90,
                "tags": ["flooring", "vinyl", "renovation"],
                "materials": [
                    "Luxury vinyl planks (calculate square footage + 10%)",
                    "Underlayment (if not attached to planks)",
                    "Transition strips for doorways",
                    "Spacers (1/4\")"
                ],
                "tools": [
                    "Tape measure",
                    "Utility knife",
                    "Square",
                    "Rubber mallet",
                    "Tapping block",
                    "Pull bar",
                    "Saw for cutting planks"
                ],
                "steps": [
                    "Remove existing flooring and clean subfloor",
                    "Allow flooring to acclimate (24-48 hours)",
                    "Install underlayment if needed",
                    "Plan your layout starting from the longest, straightest wall",
                    "Leave 1/4\" expansion gap around perimeter",
                    "Stagger end joints by at least 6 inches",
                    "Tap planks together using block and mallet",
                    "Use pull bar for last row",
                    "Install transition strips at doorways"
                ],
                "image_url": "/static/diy/vinyl_flooring.jpg",
                "tips": [
                    "Ensure subfloor is clean, dry, and level",
                    "Mix planks from different boxes for natural variation",
                    "Work in good lighting to spot alignment issues",
                    "Save leftover planks for future repairs"
                ],
                "safety": [
                    "Wear knee pads for comfort",
                    "Use gloves when handling cut planks",
                    "Keep work area clear of tripping hazards"
                ]
            },
            {
                "id": "p003",
                "title": "Install a Ceiling Fan",
                "description": "Replace an existing light fixture with an energy-efficient ceiling fan to improve air circulation and add style.",
                "difficulty": "medium",
                "category": "Electrical",
                "time_estimate": "2-3 hours",
                "cost_estimate": "$100-300",
                "popularity": 85,
                "tags": ["lighting", "electrical", "energy efficiency"],
                "materials": [
                    "Ceiling fan with mounting hardware",
                    "Wire nuts",
                    "Electrical tape",
                    "Fan-rated electrical box (if needed)"
                ],
                "tools": [
                    "Screwdrivers",
                    "Wire strippers",
                    "Voltage tester",
                    "Pliers",
                    "Ladder",
                    "Helper (recommended)"
                ],
                "steps": [
                    "Turn off power at circuit breaker",
                    "Remove existing light fixture",
                    "Verify electrical box is fan-rated (replace if not)",
                    "Assemble fan according to manufacturer instructions",
                    "Connect wiring (usually black to black, white to white, ground to ground)",
                    "Secure mounting bracket to electrical box",
                    "Attach fan motor to bracket",
                    "Install blades and light kit",
                    "Restore power and test"
                ],
                "image_url": "/static/diy/ceiling_fan.jpg",
                "tips": [
                    "Choose the right size fan for your room (room sq ft / 4 = fan diameter in inches)",
                    "For best airflow, blades should be at least 7 feet from floor, 10-12 inches from ceiling",
                    "Ensure your electrical box is rated for ceiling fans",
                    "Use a fan with a remote for convenience"
                ],
                "safety": [
                    "ALWAYS verify power is off with a voltage tester",
                    "Secure ladder on level ground",
                    "Have a helper assist with holding the fan during installation",
                    "Do not hang from the fan to test it"
                ]
            },
            {
                "id": "p004",
                "title": "Build a Raised Garden Bed",
                "description": "Create a productive garden space with a custom raised bed. Perfect for growing vegetables, herbs, or flowers.",
                "difficulty": "easy",
                "category": "Outdoor",
                "time_estimate": "2-4 hours",
                "cost_estimate": "$50-200",
                "popularity": 88,
                "tags": ["garden", "outdoor", "woodworking"],
                "materials": [
                    "Rot-resistant lumber (cedar or pressure-treated)",
                    "Galvanized deck screws",
                    "Landscape fabric",
                    "Garden soil",
                    "Compost"
                ],
                "tools": [
                    "Saw",
                    "Drill/driver",
                    "Measuring tape",
                    "Square",
                    "Level",
                    "Shovel"
                ],
                "steps": [
                    "Choose a sunny location with good drainage",
                    "Measure and mark the bed area",
                    "Cut lumber to desired dimensions (common: 4'x8')",
                    "Assemble frame with screws (pre-drill to prevent splitting)",
                    "Level the ground where bed will sit",
                    "Position frame and check level",
                    "Line bottom with landscape fabric if desired",
                    "Fill with soil/compost mix",
                    "Water thoroughly before planting"
                ],
                "image_url": "/static/diy/garden_bed.jpg",
                "tips": [
                    "Standard depth is 10-12 inches for most plants",
                    "Consider adding a drip irrigation system",
                    "For longevity, use cedar, redwood, or heat-treated lumber",
                    "Add vertical supports for trellising if growing climbing plants"
                ],
                "safety": [
                    "Wear gloves when handling lumber",
                    "Use eye protection when cutting wood",
                    "Lift with your legs when moving soil"
                ]
            },
            {
                "id": "p005",
                "title": "Upgrade Your Kitchen Faucet",
                "description": "Replace an old kitchen faucet with a modern fixture to improve functionality and update your kitchen's look.",
                "difficulty": "medium",
                "category": "Plumbing",
                "time_estimate": "1-2 hours",
                "cost_estimate": "$75-300",
                "popularity": 82,
                "tags": ["kitchen", "plumbing", "fixtures"],
                "materials": [
                    "New kitchen faucet",
                    "Plumber's putty or silicone",
                    "Teflon tape",
                    "Supply lines (if not included with faucet)"
                ],
                "tools": [
                    "Basin wrench or channel-lock pliers",
                    "Adjustable wrench",
                    "Flashlight",
                    "Bucket and towels",
                    "Putty knife"
                ],
                "steps": [
                    "Clear area under sink and place bucket to catch water",
                    "Shut off water supply valves",
                    "Disconnect supply lines from old faucet",
                    "Remove old faucet mounting nuts",
                    "Clean sink surface where old faucet was mounted",
                    "Follow manufacturer instructions to assemble new faucet",
                    "Apply plumber's putty or silicone to base of new faucet",
                    "Install new faucet from above",
                    "Secure with mounting hardware from below",
                    "Connect water supply lines",
                    "Turn on water and check for leaks"
                ],
                "image_url": "/static/diy/kitchen_faucet.jpg",
                "tips": [
                    "Take photos before disconnecting old faucet",
                    "Measure sink holes before purchasing new faucet",
                    "Consider a pull-down sprayer for added functionality",
                    "Replace supply lines while you're at it, even if not required"
                ],
                "safety": [
                    "Turn off water at shut-off valves AND verify",
                    "Keep a bucket and towels handy for water in lines",
                    "Have a second person help if working in tight spaces"
                ]
            }
        ]