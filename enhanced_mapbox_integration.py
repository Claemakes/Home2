"""
Enhanced Mapbox Integration

This module provides advanced geospatial processing using Mapbox APIs,
including geocoding, reverse geocoding, 3D building extraction,
and satellite imagery processing.
"""

import os
import json
import time
import logging
import requests
from urllib.parse import urlencode

# Configure logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('enhanced_mapbox_integration')

class MapboxIntegration:
    """
    Enhanced Mapbox integration for address validation, geocoding, and 3D data extraction
    """
    
    def __init__(self, api_key=None):
        """
        Initialize the Mapbox integration with optional API key
        
        Args:
            api_key (str): Mapbox API key
        """
        self.api_key = api_key or os.environ.get('MAPBOX_API_KEY', '')
        self.base_url = 'https://api.mapbox.com'
        
        if not self.api_key:
            logger.warning("Mapbox API key not provided or found in environment")
    
    def geocode(self, address):
        """
        Convert address to coordinates using Mapbox Geocoding API
        
        Args:
            address (str): The address to geocode
            
        Returns:
            dict: Geocoding results with coordinates and metadata
        """
        if not self.api_key:
            logger.error("Mapbox API key is required for geocoding")
            return None
            
        logger.info(f"Geocoding address: {address}")
        
        try:
            # Encode the address for URL
            encoded_address = address.replace(' ', '+')
            
            # Call Mapbox Geocoding API
            endpoint = f"{self.base_url}/geocoding/v5/mapbox.places/{encoded_address}.json"
            params = {
                'access_token': self.api_key,
                'limit': 5,
                'types': 'address,poi,place',
                'autocomplete': True
            }
            
            response = requests.get(f"{endpoint}?{urlencode(params)}")
            
            if response.status_code != 200:
                logger.error(f"Geocoding API error: {response.status_code} - {response.text}")
                return None
                
            # Parse the response
            data = response.json()
            
            # Check if we got any results
            if not data.get('features'):
                logger.warning(f"No geocoding results found for address: {address}")
                return None
                
            # Process and structure the results
            results = []
            for feature in data['features']:
                # Extract coordinates
                longitude, latitude = feature['center']
                
                # Extract address components
                place_name = feature.get('place_name', '')
                place_type = feature.get('place_type', [])
                
                # Get the context data for more details
                context = feature.get('context', [])
                context_data = {}
                
                for ctx in context:
                    if 'id' in ctx:
                        id_parts = ctx['id'].split('.')
                        if len(id_parts) >= 2:
                            context_type = id_parts[0]
                            context_data[context_type] = ctx.get('text', '')
                
                # Structure the result
                result = {
                    'coordinates': {
                        'latitude': latitude,
                        'longitude': longitude
                    },
                    'full_address': place_name,
                    'place_type': place_type[0] if place_type else None,
                    'street': feature.get('text', ''),
                    'city': context_data.get('place', ''),
                    'state': context_data.get('region', ''),
                    'country': context_data.get('country', ''),
                    'postal_code': context_data.get('postcode', ''),
                    'relevance': feature.get('relevance', 0)
                }
                
                results.append(result)
            
            return results
            
        except Exception as e:
            logger.error(f"Error in geocoding: {str(e)}")
            return None
    
    def reverse_geocode(self, latitude, longitude):
        """
        Convert coordinates to address using Mapbox Reverse Geocoding API
        
        Args:
            latitude (float): Latitude coordinate
            longitude (float): Longitude coordinate
            
        Returns:
            dict: Reverse geocoding results with address and metadata
        """
        if not self.api_key:
            logger.error("Mapbox API key is required for reverse geocoding")
            return None
            
        logger.info(f"Reverse geocoding coordinates: {latitude}, {longitude}")
        
        try:
            # Call Mapbox Reverse Geocoding API
            endpoint = f"{self.base_url}/geocoding/v5/mapbox.places/{longitude},{latitude}.json"
            params = {
                'access_token': self.api_key,
                'types': 'address'
            }
            
            response = requests.get(f"{endpoint}?{urlencode(params)}")
            
            if response.status_code != 200:
                logger.error(f"Reverse Geocoding API error: {response.status_code} - {response.text}")
                return None
                
            # Parse the response
            data = response.json()
            
            # Check if we got any results
            if not data.get('features'):
                logger.warning(f"No reverse geocoding results found for coordinates: {latitude}, {longitude}")
                return None
                
            # Get the first (most relevant) result
            feature = data['features'][0]
            
            # Extract address components
            place_name = feature.get('place_name', '')
            
            # Get the context data for more details
            context = feature.get('context', [])
            context_data = {}
            
            for ctx in context:
                if 'id' in ctx:
                    id_parts = ctx['id'].split('.')
                    if len(id_parts) >= 2:
                        context_type = id_parts[0]
                        context_data[context_type] = ctx.get('text', '')
            
            # Structure the result
            result = {
                'full_address': place_name,
                'street': feature.get('text', ''),
                'city': context_data.get('place', ''),
                'state': context_data.get('region', ''),
                'country': context_data.get('country', ''),
                'postal_code': context_data.get('postcode', '')
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error in reverse geocoding: {str(e)}")
            return None
    
    def get_static_map(self, latitude, longitude, zoom=14, width=600, height=400, style='satellite-streets-v11'):
        """
        Generate a static map image URL for the given coordinates
        
        Args:
            latitude (float): Latitude coordinate
            longitude (float): Longitude coordinate
            zoom (int): Zoom level (1-20)
            width (int): Image width in pixels
            height (int): Image height in pixels
            style (str): Map style ID
            
        Returns:
            str: URL to the static map image
        """
        if not self.api_key:
            logger.error("Mapbox API key is required for static maps")
            return None
            
        try:
            # Format the static map URL
            url = f"{self.base_url}/styles/v1/mapbox/{style}/static/{longitude},{latitude},{zoom}/{width}x{height}"
            
            # Add the access token
            url += f"?access_token={self.api_key}"
            
            return url
            
        except Exception as e:
            logger.error(f"Error generating static map URL: {str(e)}")
            return None
    
    def get_building_data(self, latitude, longitude, radius=100):
        """
        Retrieve building data for a location using Mapbox Tilequery API
        
        Args:
            latitude (float): Latitude coordinate
            longitude (float): Longitude coordinate
            radius (int): Search radius in meters
            
        Returns:
            dict: Building data including footprint, height, and type
        """
        if not self.api_key:
            logger.error("Mapbox API key is required for building data")
            return None
            
        logger.info(f"Getting building data for coordinates: {latitude}, {longitude}")
        
        try:
            # Call Mapbox Tilequery API
            endpoint = f"{self.base_url}/v4/mapbox.mapbox-streets-v8/tilequery/{longitude},{latitude}.json"
            params = {
                'access_token': self.api_key,
                'layers': 'building',
                'radius': radius
            }
            
            response = requests.get(f"{endpoint}?{urlencode(params)}")
            
            if response.status_code != 200:
                logger.error(f"Tilequery API error: {response.status_code} - {response.text}")
                return None
                
            # Parse the response
            data = response.json()
            
            # Check if we got any results
            if not data.get('features'):
                logger.warning(f"No building data found for coordinates: {latitude}, {longitude}")
                return None
                
            # Process building features
            buildings = []
            for feature in data['features']:
                properties = feature.get('properties', {})
                geometry = feature.get('geometry', {})
                
                building = {
                    'type': properties.get('type', 'building'),
                    'height': properties.get('height', 10),  # Default height if not available
                    'geometry': geometry,
                    'distance': properties.get('tilequery', {}).get('distance', 0)
                }
                
                buildings.append(building)
            
            # Sort by distance and return the closest building
            buildings.sort(key=lambda b: b['distance'])
            
            return buildings[0] if buildings else None
            
        except Exception as e:
            logger.error(f"Error retrieving building data: {str(e)}")
            return None
    
    def get_address_suggestions(self, query, limit=5):
        """
        Get address suggestions as the user types
        
        Args:
            query (str): Partial address query
            limit (int): Maximum number of suggestions to return
            
        Returns:
            list: List of address suggestions
        """
        if not self.api_key:
            logger.error("Mapbox API key is required for address suggestions")
            return []
            
        if not query or len(query) < 3:
            return []
            
        logger.info(f"Getting address suggestions for query: {query}")
        
        try:
            # Encode the query for URL
            encoded_query = query.replace(' ', '+')
            
            # Call Mapbox Geocoding API with autocomplete
            endpoint = f"{self.base_url}/geocoding/v5/mapbox.places/{encoded_query}.json"
            params = {
                'access_token': self.api_key,
                'limit': limit,
                'types': 'address',
                'autocomplete': True
            }
            
            response = requests.get(f"{endpoint}?{urlencode(params)}")
            
            if response.status_code != 200:
                logger.error(f"Geocoding API error: {response.status_code} - {response.text}")
                return []
                
            # Parse the response
            data = response.json()
            
            # Check if we got any results
            if not data.get('features'):
                return []
                
            # Extract and format suggestions
            suggestions = []
            for feature in data['features']:
                suggestion = {
                    'text': feature.get('place_name', ''),
                    'place_type': feature.get('place_type', ['address'])[0],
                    'coordinates': {
                        'longitude': feature['center'][0],
                        'latitude': feature['center'][1]
                    }
                }
                
                suggestions.append(suggestion)
            
            return suggestions
            
        except Exception as e:
            logger.error(f"Error getting address suggestions: {str(e)}")
            return []
    
    def get_directions(self, origin_lat, origin_lng, dest_lat, dest_lng, mode='driving'):
        """
        Get directions between two points
        
        Args:
            origin_lat (float): Origin latitude
            origin_lng (float): Origin longitude
            dest_lat (float): Destination latitude
            dest_lng (float): Destination longitude
            mode (str): Transportation mode (driving, walking, cycling)
            
        Returns:
            dict: Directions data including route, duration, and distance
        """
        if not self.api_key:
            logger.error("Mapbox API key is required for directions")
            return None
            
        logger.info(f"Getting directions from {origin_lat},{origin_lng} to {dest_lat},{dest_lng}")
        
        try:
            # Validate the mode
            valid_modes = ['driving', 'walking', 'cycling']
            if mode not in valid_modes:
                mode = 'driving'
            
            # Call Mapbox Directions API
            endpoint = f"{self.base_url}/directions/v5/mapbox/{mode}/{origin_lng},{origin_lat};{dest_lng},{dest_lat}"
            params = {
                'access_token': self.api_key,
                'geometries': 'geojson',
                'steps': 'true',
                'overview': 'full'
            }
            
            response = requests.get(f"{endpoint}?{urlencode(params)}")
            
            if response.status_code != 200:
                logger.error(f"Directions API error: {response.status_code} - {response.text}")
                return None
                
            # Parse the response
            data = response.json()
            
            # Check if we got any routes
            if not data.get('routes'):
                logger.warning(f"No routes found between coordinates")
                return None
                
            # Get the first (optimal) route
            route = data['routes'][0]
            
            # Structure the result
            result = {
                'distance': route.get('distance', 0),  # in meters
                'duration': route.get('duration', 0),  # in seconds
                'geometry': route.get('geometry', {}),
                'steps': []
            }
            
            # Process route steps
            if 'legs' in route and route['legs']:
                for leg in route['legs']:
                    for step in leg.get('steps', []):
                        result['steps'].append({
                            'instruction': step.get('maneuver', {}).get('instruction', ''),
                            'distance': step.get('distance', 0),
                            'duration': step.get('duration', 0)
                        })
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting directions: {str(e)}")
            return None