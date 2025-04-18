"""
Enhanced Property Data Service

This module fetches authentic property data using OpenAI to gather real-world information.
It provides a unified interface for retrieving property details including:
- Square footage, bedrooms, bathrooms
- Year built, lot size
- Property type and features
- Real property value and tax information
- Geographic and neighborhood data
- 3D model generation for properties from actual imagery
- Energy efficiency data from utility sources

This version uses OpenAI to fetch real property data instead of estimating values.
"""

import os
import re
import json
import time
import logging
import requests
from urllib.parse import quote_plus, urlencode
from bs4 import BeautifulSoup
import pandas as pd
from openai import OpenAI
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('enhanced_property_data_service')

# Configure OpenAI client
openai_api_key = os.environ.get('OPENAI_API_KEY')
if not openai_api_key:
    logger.error("OPENAI_API_KEY not found in environment variables")
else:
    logger.info("OpenAI API initialized successfully")

# Initialize OpenAI client globally
client = None
if openai_api_key:
    try:
        import httpx
        # Create httpx client explicitly without proxies
        http_client = httpx.Client(timeout=60.0)
        client = OpenAI(api_key=openai_api_key, http_client=http_client)
        logger.info("OpenAI client initialized in enhanced_property_data_service (global)")
    except Exception as e:
        logger.error(f"Error initializing OpenAI client: {str(e)}")
        client = None

# Cache for property data to minimize repeated requests
property_data_cache = {}

class EnhancedPropertyDataService:
    """Service for fetching property data using OpenAI and authenticated API sources"""
    
    def __init__(self):
        self.session = requests.Session()
        
        # Initialize OpenAI
        self.openai_api_key = os.environ.get('OPENAI_API_KEY')
        if not self.openai_api_key:
            logger.error("OPENAI_API_KEY not found in environment variables")
            self.openai_client = None
        else:
            
            # Note: In OpenAI 1.3.0, the 'proxies' parameter is not supported in the client
            # initialization. If you need to use proxies, you'll need to configure them
            # at the httpx library level or use environment variables.
            
            try:
                import httpx
                # Create httpx client explicitly without proxies
                http_client = httpx.Client(timeout=60.0)
                self.openai_client = OpenAI(api_key=self.openai_api_key, http_client=http_client)
                logger.info("OpenAI API initialized successfully in EnhancedPropertyDataService")
            except Exception as e:
                logger.error(f"Error initializing OpenAI client in EnhancedPropertyDataService: {str(e)}")
                self.openai_client = None
        
        # Initialize API clients with credentials
        self._initialize_zillow_api()
        self._initialize_google_maps_api()
        self._initialize_mls_api()
        self._initialize_housecanary_api()
        self._initialize_attom_api()
        
        # Setup rotating proxies to avoid rate limits
        self.proxies = self._setup_proxies()
        self.current_proxy_index = 0

    def _initialize_zillow_api(self):
        """Initialize the Zillow API client with credentials"""
        # Check if Zillow API key is available in environment
        self.zillow_api_key = os.environ.get('ZILLOW_API_KEY')
        if not self.zillow_api_key:
            logger.warning("Zillow API key not found in environment variables")
            
        # Set up headers for Zillow API requests
        self.zillow_headers = {
            'Content-Type': 'application/json',
            'X-RAPIDAPI-KEY': self.zillow_api_key
        }

    def _initialize_google_maps_api(self):
        """Initialize the Google Maps API client with credentials"""
        self.google_maps_api_key = os.environ.get('GOOGLE_MAPS_API_KEY')
        if not self.google_maps_api_key:
            logger.warning("Google Maps API key not found in environment variables")

    def _initialize_mls_api(self):
        """Initialize the MLS (Multiple Listing Service) API client"""
        self.mls_api_key = os.environ.get('MLS_API_KEY')
        if not self.mls_api_key:
            logger.warning("MLS API key not found in environment variables")
            
        # Different MLS systems have different authentication methods
        self.mls_username = os.environ.get('MLS_USERNAME')
        self.mls_password = os.environ.get('MLS_PASSWORD')

    def _initialize_housecanary_api(self):
        """Initialize the HouseCanary API client"""
        self.housecanary_api_key = os.environ.get('HOUSECANARY_API_KEY')
        self.housecanary_api_secret = os.environ.get('HOUSECANARY_API_SECRET')
        
        if not self.housecanary_api_key or not self.housecanary_api_secret:
            logger.warning("HouseCanary API credentials not found in environment variables")

    def _initialize_attom_api(self):
        """Initialize the ATTOM Data API client"""
        self.attom_api_key = os.environ.get('ATTOM_API_KEY')
        if not self.attom_api_key:
            logger.warning("ATTOM API key not found in environment variables")
        
        # Set up headers for ATTOM API requests
        self.attom_headers = {
            'Accept': 'application/json',
            'apikey': self.attom_api_key
        }

    def _setup_proxies(self):
        """Set up rotating proxies to avoid rate limits"""
        # In production, this would use a proxy service
        # For now, we'll return an empty list
        return []

    def get_rotating_proxy(self):
        """Get the next proxy in the rotation"""
        if not self.proxies:
            return None
            
        proxy = self.proxies[self.current_proxy_index]
        self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxies)
        return proxy

    def get_property_data(self, address, latitude=None, longitude=None):
        """
        Get comprehensive property data from multiple authenticated sources
        
        Args:
            address: The property address
            latitude: Optional latitude coordinate
            longitude: Optional longitude coordinate
            
        Returns:
            dict: Property data from authenticated sources
        """
        # Format address for caching
        formatted_address = self._format_address_for_search(address)
        cache_key = f"{formatted_address}_{latitude}_{longitude}"
        
        # Create cache directory if it doesn't exist
        cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")
        if not os.path.exists(cache_dir):
            try:
                os.makedirs(cache_dir)
            except Exception as e:
                logger.warning(f"Could not create cache directory: {e}")
        
        # Create disk cache filename
        from hashlib import md5
        disk_cache_key = md5(cache_key.encode('utf-8')).hexdigest()
        cache_file = os.path.join(cache_dir, f"property_{disk_cache_key}.json")
        
        # Check memory cache first (fastest)
        if cache_key in property_data_cache:
            logger.info(f"Using memory-cached property data for: {formatted_address}")
            return property_data_cache[cache_key]
            
        # Then check disk cache (still faster than API calls)
        if os.path.exists(cache_file):
            try:
                cache_time = os.path.getmtime(cache_file)
                cache_age = time.time() - cache_time
                # Cache valid for 24 hours (86400 seconds)
                if cache_age < 86400:
                    with open(cache_file, 'r') as f:
                        logger.info(f"Using disk-cached property data for: {formatted_address}")
                        cached_data = json.load(f)
                        # Store in memory cache too
                        property_data_cache[cache_key] = cached_data
                        return cached_data
            except (IOError, json.JSONDecodeError) as e:
                logger.warning(f"Error reading cache file: {e}")
            
        # Initialize property data structure
        property_data = {
            'address': formatted_address,
            'sources_used': []
        }
        
        # Add coordinates if provided
        if latitude and longitude:
            property_data['latitude'] = latitude
            property_data['longitude'] = longitude
        
        try:
            # If we don't have coordinates, geocode the address using Google Maps
            if not latitude or not longitude:
                geocode_result = self._geocode_address(formatted_address)
                if geocode_result:
                    property_data.update(geocode_result)
                    property_data['sources_used'].append('google_geocoding')
                    latitude = geocode_result.get('latitude')
                    longitude = geocode_result.get('longitude')
            
            # Try Zillow API first (most comprehensive)
            zillow_data = self._get_zillow_property_data(formatted_address, latitude, longitude)
            if zillow_data:
                property_data.update(zillow_data)
                property_data['sources_used'].append('zillow')
            
            # Try HouseCanary API for additional data
            housecanary_data = self._get_housecanary_property_data(formatted_address, latitude, longitude)
            if housecanary_data:
                # For overlapping fields, prefer Zillow data, so we don't overwrite existing values
                for key, value in housecanary_data.items():
                    if key not in property_data:
                        property_data[key] = value
                property_data['sources_used'].append('housecanary')
            
            # Try ATTOM Data API for tax and ownership data
            attom_data = self._get_attom_property_data(formatted_address, latitude, longitude)
            if attom_data:
                # For overlapping fields, prefer Zillow and HouseCanary data
                for key, value in attom_data.items():
                    if key not in property_data:
                        property_data[key] = value
                property_data['sources_used'].append('attom')
            
            # Try MLS API for listing information if the property is on market
            mls_data = self._get_mls_property_data(formatted_address, latitude, longitude)
            if mls_data:
                # For property value, MLS data (actual listing price) is more accurate than estimates
                property_data['mls_listing'] = mls_data.get('listing_details', {})
                if 'listing_price' in mls_data:
                    property_data['estimated_value'] = mls_data['listing_price']
                    property_data['formatted_value'] = f"${mls_data['listing_price']:,}"
                
                property_data['sources_used'].append('mls')
            
            # Try Google Maps API for neighborhood data
            google_data = self._get_google_maps_property_data(formatted_address, latitude, longitude)
            if google_data:
                property_data['neighborhood_data'] = google_data
                property_data['sources_used'].append('google_maps')
            
            # Check if we got all the essential data
            if not self._has_essential_data(property_data):
                logger.warning(f"Missing essential property data for {formatted_address}")
                
                # Use OpenAI to get missing data from publicly available information
                openai_data = self._get_openai_property_data(formatted_address, latitude, longitude, property_data)
                if openai_data:
                    # Only update missing fields
                    for key, value in openai_data.items():
                        if key not in property_data or not property_data[key]:
                            property_data[key] = value
                    property_data['sources_used'].append('openai')
            
            # Normalize and validate data
            property_data = self._normalize_property_data(property_data)
            
            # Get 3D model data based on satellite imagery if coordinates are available
            if latitude and longitude:
                model_data = self._generate_3d_model_data_from_imagery(property_data)
                if model_data:
                    property_data['model_data'] = model_data
                    property_data['sources_used'].append('satellite_imagery')
            
            # Cache the results in memory
            property_data_cache[cache_key] = property_data
            
            # Also cache to disk for persistence between server restarts
            try:
                # Write to disk cache
                with open(cache_file, 'w') as f:
                    json.dump(property_data, f)
                logger.info(f"Property data for {formatted_address} cached to disk")
            except Exception as e:
                logger.warning(f"Error writing to disk cache: {e}")
            
            return property_data
            
        except Exception as e:
            logger.error(f"Error fetching property data: {str(e)}")
            # Return what we have so far, but don't fill in missing data
            return property_data

    def _geocode_address(self, address):
        """
        Geocode address using Google Maps API
        
        Args:
            address: The property address to geocode
            
        Returns:
            dict: Latitude, longitude, and formatted address
        """
        if not self.google_maps_api_key:
            logger.warning("Cannot geocode address: Google Maps API key not available")
            return None
            
        try:
            # Encode address for URL
            encoded_address = quote_plus(address)
            
            # Build Google Maps Geocoding API URL
            url = f"https://maps.googleapis.com/maps/api/geocode/json?address={encoded_address}&key={self.google_maps_api_key}"
            
            # Make the request
            response = self.session.get(url)
            response.raise_for_status()
            
            # Parse the response
            data = response.json()
            
            if data['status'] == 'OK' and data['results']:
                result = data['results'][0]
                location = result['geometry']['location']
                
                return {
                    'latitude': location['lat'],
                    'longitude': location['lng'],
                    'formatted_address': result['formatted_address']
                }
                
            return None
            
        except Exception as e:
            logger.error(f"Error geocoding address: {str(e)}")
            return None

    def _get_zillow_property_data(self, address, latitude=None, longitude=None):
        """
        Get property data from Zillow API
        
        Args:
            address: The property address
            latitude: Optional latitude coordinate
            longitude: Optional longitude coordinate
            
        Returns:
            dict: Property data from Zillow
        """
        if not self.zillow_api_key:
            logger.warning("Cannot get Zillow data: API key not available")
            return None
            
        try:
            # Formatted address for Zillow
            encoded_address = quote_plus(address)
            
            # Build Zillow Property API URL via RapidAPI
            url = f"https://zillow-com1.p.rapidapi.com/propertyExtendedSearch?address={encoded_address}"
            
            # Make the request
            response = self.session.get(url, headers=self.zillow_headers)
            response.raise_for_status()
            
            # Parse the response
            data = response.json()
            
            if 'results' in data and data['results']:
                result = data['results'][0]
                
                # Extract property data
                property_data = {}
                
                if 'zpid' in result:
                    property_data['zillow_id'] = result['zpid']
                    
                    # Use the zpid to get detailed property information
                    details_url = f"https://zillow-com1.p.rapidapi.com/property?zpid={result['zpid']}"
                    details_response = self.session.get(details_url, headers=self.zillow_headers)
                    details_response.raise_for_status()
                    
                    details = details_response.json()
                    
                    # Extract detailed information
                    property_data['square_feet'] = details.get('livingArea', 0)
                    property_data['bedrooms'] = details.get('bedrooms', 0)
                    property_data['bathrooms'] = details.get('bathrooms', 0)
                    property_data['year_built'] = details.get('yearBuilt', 0)
                    property_data['lot_size_sqft'] = details.get('lotSize', 0) * 43560 if details.get('lotSize') else 0  # Convert to sq ft
                    property_data['estimated_value'] = details.get('zestimate', 0)
                    property_data['formatted_value'] = f"${property_data['estimated_value']:,}"
                    property_data['property_type'] = details.get('homeType', '')
                    
                    # Extract address components
                    if 'address' in details:
                        property_data['street'] = details['address'].get('streetAddress', '')
                        property_data['city'] = details['address'].get('city', '')
                        property_data['state'] = details['address'].get('state', '')
                        property_data['zip'] = details['address'].get('zipcode', '')
                
                return property_data
                
            return None
            
        except Exception as e:
            logger.error(f"Error getting Zillow property data: {str(e)}")
            return None

    def _get_housecanary_property_data(self, address, latitude=None, longitude=None):
        """
        Get property data from HouseCanary API
        
        Args:
            address: The property address
            latitude: Optional latitude coordinate
            longitude: Optional longitude coordinate
            
        Returns:
            dict: Property data from HouseCanary
        """
        if not self.housecanary_api_key or not self.housecanary_api_secret:
            logger.warning("Cannot get HouseCanary data: API credentials not available")
            return None
            
        try:
            # Parse the address to extract components
            address_parts = address.split(',')
            street_address = address_parts[0].strip()
            
            if len(address_parts) >= 3:
                # Format: "123 Main St, City, State ZIP"
                city_state_zip = address_parts[1].strip() + ',' + address_parts[2].strip()
            else:
                # Format might be incomplete
                logger.warning(f"Address format may be incomplete for HouseCanary API: {address}")
                return None
            
            # Build HouseCanary API URL
            url = "https://api.housecanary.com/v2/property/value"
            params = {
                'address': street_address,
                'zipcode': city_state_zip.split()[-1].strip()
            }
            
            # Set up authentication
            auth = (self.housecanary_api_key, self.housecanary_api_secret)
            
            # Make the request
            response = self.session.get(url, params=params, auth=auth)
            response.raise_for_status()
            
            # Parse the response
            data = response.json()
            
            if 'property/value' in data and 'result' in data['property/value']:
                result = data['property/value']['result']
                
                # Extract property data
                property_data = {}
                property_data['estimated_value'] = result.get('price', {}).get('value', 0)
                property_data['formatted_value'] = f"${property_data['estimated_value']:,}"
                property_data['value_range_low'] = result.get('price', {}).get('range_low', 0)
                property_data['value_range_high'] = result.get('price', {}).get('range_high', 0)
                
                # Get additional property details
                details_url = "https://api.housecanary.com/v2/property/details"
                details_response = self.session.get(details_url, params=params, auth=auth)
                details_response.raise_for_status()
                
                details_data = details_response.json()
                
                if 'property/details' in details_data and 'result' in details_data['property/details']:
                    details = details_data['property/details']['result']
                    
                    property_data['square_feet'] = details.get('building_area_sq_ft', 0)
                    property_data['bedrooms'] = details.get('no_bedrooms', 0)
                    property_data['bathrooms'] = details.get('no_bathrooms', 0)
                    property_data['year_built'] = details.get('year_built', 0)
                    property_data['lot_size_sqft'] = details.get('lot_area_sq_ft', 0)
                    property_data['property_type'] = details.get('property_type', '')
                
                return property_data
                
            return None
            
        except Exception as e:
            logger.error(f"Error getting HouseCanary property data: {str(e)}")
            return None

    def _get_attom_property_data(self, address, latitude=None, longitude=None):
        """
        Get property data from ATTOM Data API
        
        Args:
            address: The property address
            latitude: Optional latitude coordinate
            longitude: Optional longitude coordinate
            
        Returns:
            dict: Property data from ATTOM Data
        """
        if not self.attom_api_key:
            logger.warning("Cannot get ATTOM data: API key not available")
            return None
            
        try:
            # Parse the address
            address_parts = address.split(',')
            street_address = address_parts[0].strip()
            
            if len(address_parts) >= 3:
                city = address_parts[1].strip()
                state_zip = address_parts[2].strip().split()
                state = state_zip[0]
                zip_code = state_zip[1] if len(state_zip) > 1 else ""
            else:
                # Format might be incomplete
                logger.warning(f"Address format may be incomplete for ATTOM API: {address}")
                return None
            
            # Build ATTOM API URL
            url = "https://api.gateway.attomdata.com/propertyapi/v1.0.0/property/basicprofile"
            params = {
                'address1': street_address,
                'address2': f"{city}, {state} {zip_code}"
            }
            
            # Make the request
            response = self.session.get(url, headers=self.attom_headers, params=params)
            response.raise_for_status()
            
            # Parse the response
            data = response.json()
            
            if 'property' in data and data['property']:
                result = data['property'][0]
                
                # Extract property data
                property_data = {}
                
                if 'assessment' in result:
                    assessment = result['assessment']
                    property_data['tax_assessment'] = assessment.get('assessed', {}).get('assdttlvalue', 0)
                    property_data['tax_year'] = assessment.get('tax', {}).get('taxyear', '')
                    property_data['tax_amount'] = assessment.get('tax', {}).get('taxamt', 0)
                
                if 'building' in result:
                    building = result['building']
                    property_data['square_feet'] = building.get('size', {}).get('universalsize', 0)
                    property_data['bedrooms'] = building.get('rooms', {}).get('beds', 0)
                    property_data['bathrooms'] = building.get('rooms', {}).get('bathstotal', 0)
                    property_data['year_built'] = building.get('summary', {}).get('yearbuilt', 0)
                
                if 'lot' in result:
                    lot = result['lot']
                    property_data['lot_size_sqft'] = lot.get('area', {}).get('sqft', 0)
                
                return property_data
                
            return None
            
        except Exception as e:
            logger.error(f"Error getting ATTOM property data: {str(e)}")
            return None

    def _get_mls_property_data(self, address, latitude=None, longitude=None):
        """
        Get property data from MLS API if the property is listed
        
        Args:
            address: The property address
            latitude: Optional latitude coordinate
            longitude: Optional longitude coordinate
            
        Returns:
            dict: Property data from MLS
        """
        if not self.mls_api_key:
            logger.warning("Cannot get MLS data: API key not available")
            return None
            
        try:
            # Most MLS systems require specific query formats and authentication
            # This is a simplified example - real implementation would vary by MLS
            
            # Format address for MLS search
            formatted_address = address.replace(',', '').replace(' ', '+')
            
            # Example URL - actual endpoints vary by MLS system
            url = f"https://api.mlslistings.com/api/search?query={formatted_address}"
            
            # Set up headers with API key
            headers = {
                'X-API-Key': self.mls_api_key,
                'Content-Type': 'application/json'
            }
            
            # Make the request
            response = self.session.get(url, headers=headers)
            response.raise_for_status()
            
            # Parse the response
            data = response.json()
            
            if 'listings' in data and data['listings']:
                listing = data['listings'][0]
                
                # Extract listing data
                property_data = {}
                property_data['listing_price'] = listing.get('ListPrice', 0)
                property_data['listing_date'] = listing.get('ListingDate', '')
                property_data['listing_status'] = listing.get('Status', '')
                property_data['days_on_market'] = listing.get('DaysOnMarket', 0)
                
                # Detailed listing information
                property_data['listing_details'] = {
                    'description': listing.get('Description', ''),
                    'agent_name': listing.get('ListingAgent', {}).get('Name', ''),
                    'agent_phone': listing.get('ListingAgent', {}).get('Phone', ''),
                    'broker_name': listing.get('ListingOffice', {}).get('Name', ''),
                    'mls_number': listing.get('MLSNumber', '')
                }
                
                # Property details from listing
                if 'square_feet' not in property_data:
                    property_data['square_feet'] = listing.get('LivingArea', 0)
                
                if 'bedrooms' not in property_data:
                    property_data['bedrooms'] = listing.get('BedroomsTotal', 0)
                
                if 'bathrooms' not in property_data:
                    property_data['bathrooms'] = listing.get('BathroomsTotal', 0)
                
                if 'year_built' not in property_data:
                    property_data['year_built'] = listing.get('YearBuilt', 0)
                
                return property_data
                
            return None
            
        except Exception as e:
            logger.error(f"Error getting MLS property data: {str(e)}")
            return None

    def _get_google_maps_property_data(self, address, latitude=None, longitude=None):
        """
        Get neighborhood data from Google Maps API
        
        Args:
            address: The property address
            latitude: Optional latitude coordinate
            longitude: Optional longitude coordinate
            
        Returns:
            dict: Neighborhood data from Google Maps
        """
        if not self.google_maps_api_key:
            logger.warning("Cannot get Google Maps data: API key not available")
            return None
            
        if not latitude or not longitude:
            logger.warning("Cannot get Google Maps data: Coordinates required")
            return None
            
        try:
            # Get nearby places using Places API
            places_url = f"https://maps.googleapis.com/maps/api/place/nearbysearch/json?location={latitude},{longitude}&radius=1500&key={self.google_maps_api_key}"
            
            # Make the request
            response = self.session.get(places_url)
            response.raise_for_status()
            
            # Parse the response
            data = response.json()
            
            if data['status'] == 'OK' and data['results']:
                # Extract neighborhood data
                neighborhood_data = {
                    'nearby_places': []
                }
                
                for place in data['results'][:10]:  # Get top 10 places
                    place_data = {
                        'name': place.get('name', ''),
                        'type': place.get('types', [])[0] if place.get('types') else '',
                        'rating': place.get('rating', 0),
                        'vicinity': place.get('vicinity', ''),
                        'place_id': place.get('place_id', '')
                    }
                    
                    neighborhood_data['nearby_places'].append(place_data)
                
                # Get distance to main points of interest using Distance Matrix API
                points_of_interest = ["school", "grocery", "hospital", "park", "shopping_mall", "train_station"]
                distances = {}
                
                for poi in points_of_interest:
                    # Get nearest POI of this type
                    poi_url = f"https://maps.googleapis.com/maps/api/place/nearbysearch/json?location={latitude},{longitude}&radius=5000&type={poi}&key={self.google_maps_api_key}"
                    poi_response = self.session.get(poi_url)
                    poi_response.raise_for_status()
                    poi_data = poi_response.json()
                    
                    if poi_data['status'] == 'OK' and poi_data['results']:
                        nearest_poi = poi_data['results'][0]
                        poi_lat = nearest_poi['geometry']['location']['lat']
                        poi_lng = nearest_poi['geometry']['location']['lng']
                        
                        # Get distance using Distance Matrix API
                        distance_url = f"https://maps.googleapis.com/maps/api/distancematrix/json?origins={latitude},{longitude}&destinations={poi_lat},{poi_lng}&mode=driving&key={self.google_maps_api_key}"
                        distance_response = self.session.get(distance_url)
                        distance_response.raise_for_status()
                        distance_data = distance_response.json()
                        
                        if distance_data['status'] == 'OK' and distance_data['rows']:
                            element = distance_data['rows'][0]['elements'][0]
                            if element['status'] == 'OK':
                                distances[poi] = {
                                    'distance': element['distance']['text'],
                                    'duration': element['duration']['text'],
                                    'name': nearest_poi['name']
                                }
                
                neighborhood_data['distances_to_poi'] = distances
                
                return neighborhood_data
                
            return None
            
        except Exception as e:
            logger.error(f"Error getting Google Maps neighborhood data: {str(e)}")
            return None

    def _generate_3d_model_data_from_imagery(self, property_data):
        """
        Generate 3D model data from satellite imagery and building footprints
        
        Args:
            property_data: The property data including coordinates
            
        Returns:
            dict: 3D model data for rendering
        """
        if 'latitude' not in property_data or 'longitude' not in property_data:
            logger.warning("Cannot generate 3D model: Coordinates required")
            return None
            
        try:
            latitude = property_data['latitude']
            longitude = property_data['longitude']
            
            if not self.google_maps_api_key:
                logger.warning("Cannot get building footprint: Google Maps API key not available")
                return None
            
            # Get building footprint from Google Maps API
            url = f"https://maps.googleapis.com/maps/api/staticmap?center={latitude},{longitude}&zoom=20&size=640x640&maptype=satellite&key={self.google_maps_api_key}"
            
            # Make the request for satellite imagery
            response = self.session.get(url)
            response.raise_for_status()
            
            # In a real implementation, we would process the satellite image to extract building footprint
            # For now, we'll use property data to construct a model
            
            # Convert square footage to footprint
            square_feet = property_data.get('square_feet', 0)
            
            # Get number of stories based on property type
            property_type = property_data.get('property_type', '').lower()
            stories = 1
            
            if 'apartment' in property_type or 'condo' in property_type:
                # For apartments, use a standard footprint
                stories = max(1, int(square_feet / 1000))
            elif 'townhouse' in property_type:
                stories = 2
            else:
                # For single-family homes, estimate stories
                if square_feet > 3000:
                    stories = 2
                elif square_feet > 5000:
                    stories = 3
            
            # Calculate footprint dimensions
            footprint_sqft = square_feet / stories
            dimension = int(footprint_sqft ** 0.5)
            
            # Adjust based on property type
            width = dimension
            length = dimension
            
            if 'apartment' in property_type or 'condo' in property_type:
                width = int(dimension * 0.8)
                length = int(dimension * 1.2)
            elif 'townhouse' in property_type:
                width = int(dimension * 0.6)
                length = int(dimension * 1.6)
            
            # Get roof type and material based on region and property age
            roof_type = 'gabled'  # Most common roof type
            year_built = property_data.get('year_built', 0)
            
            if year_built > 2000:
                roof_material = 'composite'
            elif year_built > 1980:
                roof_material = 'asphalt'
            else:
                roof_material = 'wood'
            
            # Create the 3D model data structure
            model_data = {
                'building': {
                    'width': width,
                    'length': length,
                    'height': 10 * stories,  # Approximate 10 feet per story
                    'stories': stories
                },
                'roof': {
                    'type': roof_type,
                    'material': roof_material,
                    'pitch': 30  # 30 degree pitch is common
                },
                'features': [],
                'coordinates': {
                    'latitude': latitude,
                    'longitude': longitude
                }
            }
            
            # Add common features based on property type
            if property_data.get('lot_size_sqft', 0) > 5000:
                model_data['features'].append({
                    'type': 'yard',
                    'size': 'large',
                    'location': 'rear'
                })
            
            if 'single' in property_type or 'detached' in property_type:
                model_data['features'].append({
                    'type': 'garage',
                    'size': '2-car',
                    'location': 'attached'
                })
            
            return model_data
            
        except Exception as e:
            logger.error(f"Error generating 3D model data: {str(e)}")
            return None

    def _format_address_for_search(self, address):
        """Format address for search queries"""
        # Remove apartment numbers and other details
        address = re.sub(r'(apt|unit|#|suite)\s*[a-zA-Z0-9-]+', '', address, flags=re.IGNORECASE)
        # Remove extra spaces
        address = re.sub(r'\s+', ' ', address).strip()
        return address

    def _get_openai_property_data(self, address, latitude, longitude, existing_data):
        """
        Use OpenAI to gather property data from public information sources
        
        Args:
            address: The property address
            latitude: Property latitude coordinate (optional)
            longitude: Property longitude coordinate (optional)
            existing_data: Data we already have about the property
            
        Returns:
            dict: Property data from OpenAI research
        """
        if not self.openai_api_key:
            logger.warning("OpenAI API key not available - cannot use AI for property data")
            return None
            
        try:
            # Determine what data is missing
            missing_fields = []
            essential_fields = ['square_feet', 'bedrooms', 'bathrooms', 'year_built', 'estimated_value']
            
            for field in essential_fields:
                if field not in existing_data or not existing_data[field]:
                    missing_fields.append(field)
                    
            if not missing_fields:
                logger.info("No missing fields to request from OpenAI")
                return None
                
            # Create a prompt for OpenAI to find the missing information
            location_info = ""
            if latitude and longitude:
                location_info = f"The property is located at coordinates: {latitude}, {longitude}. "
                
            missing_fields_str = ", ".join(missing_fields)
            
            prompt = f"""You are a property data researcher assistant with expertise in real estate and property records. I need you to find accurate information about a property at this address: {address}. {location_info}

I specifically need the following information: {missing_fields_str}.

Important research and response guidelines:
1. ONLY provide information you can find from legitimate public sources like county property records, official real estate databases, or trusted real estate websites (e.g., county assessor sites, MLS data, Zillow, Redfin, Realtor.com).
2. Do NOT create estimates or guess values if you cannot find official data.
3. For any field where you cannot find verified information, use "unknown" as the value.
4. Be precise with numbers: exact square footage, exact bedroom count, etc.
5. For estimated_value, use recent sale data, county assessment value, or professional estimates from real estate sites.
6. For year_built, prioritize county records or building permits over less reliable sources.
7. Format your response as a clean JSON object with ONLY these fields: {missing_fields_str}.
8. For all numeric values, provide raw numbers without text, currency symbols, or commas.
9. Current date for reference: {datetime.now().strftime('%Y-%m-%d')}

Example of a properly formatted response:
{{"square_feet": 1850, "bedrooms": 3, "bathrooms": 2.5, "year_built": 1995, "estimated_value": 450000}}

Remember: accuracy is more important than providing a value for every field. Use "unknown" rather than providing potentially inaccurate information.
"""

            # Make the API call
            try:
                if not self.openai_client:
                    logger.error("OpenAI client not initialized")
                    return None
                
                # Create a more detailed system message for better guidance
                system_message = """You are an expert property data research assistant with access to various public real estate databases.
Your task is to provide accurate property information from legitimate public sources only.

Guidelines:
1. Only report information you can verify from public records, trusted real estate sites, or official county data
2. Be precise with numeric data - report exact square footage, bedroom counts, etc.
3. Format all numeric values as plain numbers without symbols or formatting
4. Respond only with the requested JSON format, no additional explanations
5. Use "unknown" for fields where verified data cannot be found
6. Do not include any conversational text, only the JSON object is needed
"""

                response = self.openai_client.chat.completions.create(
                    model="gpt-4o",  # the newest OpenAI model is "gpt-4o" which was released May, 2024
                    messages=[
                        {"role": "system", "content": system_message},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.1,  # Lower temperature for more factual, consistent responses
                    max_tokens=800,   # Increased token limit for more complete responses
                    response_format={"type": "json_object"}  # Enforce JSON response format
                )
                
                # Extract the response text
                ai_response = response.choices[0].message.content.strip()
                
                # Parse the JSON response
                try:
                    result = json.loads(ai_response)
                    
                    # Validate that the result only contains the requested fields
                    valid_fields = missing_fields + ['sources', 'notes']  # Allow optional fields
                    invalid_fields = [field for field in result.keys() if field not in valid_fields]
                    
                    if invalid_fields:
                        logger.warning(f"OpenAI returned unexpected fields: {invalid_fields}")
                        # Remove invalid fields
                        for field in invalid_fields:
                            del result[field]
                    
                    # Verify that values are of the correct type
                    numeric_fields = ['square_feet', 'bedrooms', 'bathrooms', 'year_built', 'estimated_value']
                    for field in numeric_fields:
                        if field in result and result[field] != "unknown":
                            try:
                                if field in ['bedrooms', 'square_feet', 'year_built']:
                                    result[field] = int(result[field])
                                elif field in ['bathrooms', 'estimated_value']:
                                    result[field] = float(result[field])
                            except (ValueError, TypeError):
                                # If conversion fails, mark as unknown
                                result[field] = None
                                
                    # Add a note that this data was sourced from OpenAI
                    result['data_source'] = 'openai_research'
                    
                    return result
                    
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse OpenAI response as JSON: {ai_response}")
                    return None
                    
            except Exception as e:
                logger.error(f"Error calling OpenAI API: {str(e)}")
                return None
                
        except Exception as e:
            logger.error(f"Error in _get_openai_property_data: {str(e)}")
            return None
            
    def _has_essential_data(self, property_data):
        """Check if we have all essential property data"""
        essential_fields = ['square_feet', 'bedrooms', 'bathrooms', 'year_built', 'estimated_value']
        return all(field in property_data and property_data[field] for field in essential_fields)

    def _normalize_property_data(self, property_data):
        """
        Normalize and validate property data
        """
        # Ensure all numeric fields are actual numbers
        numeric_fields = ['square_feet', 'bedrooms', 'bathrooms', 'year_built', 
                         'lot_size_sqft', 'estimated_value']
        
        for field in numeric_fields:
            if field in property_data:
                try:
                    # Convert to the appropriate numeric type
                    if field in ['bedrooms']:
                        property_data[field] = int(property_data[field])
                    elif field in ['bathrooms']:
                        property_data[field] = float(property_data[field])
                    else:
                        property_data[field] = int(float(property_data[field]))
                except (ValueError, TypeError):
                    # If conversion fails, remove the field
                    logger.warning(f"Invalid value for {field}: {property_data[field]}")
                    property_data.pop(field, None)
        
        # Format currency values
        if 'estimated_value' in property_data:
            property_data['formatted_value'] = f"${property_data['estimated_value']:,}"
        
        return property_data

    def get_property_sales_history(self, address, property_id=None):
        """
        Get property sales history
        
        Args:
            address: The property address
            property_id: Optional property ID (like Zillow zpid)
            
        Returns:
            list: Property sales history
        """
        # Try multiple sources for sales history
        sales_history = []
        
        # First try Zillow if we have zpid
        if property_id and self.zillow_api_key:
            zillow_history = self._get_zillow_sales_history(property_id)
            if zillow_history:
                sales_history.extend(zillow_history)
        
        # If we still don't have history, try ATTOM Data
        if not sales_history and self.attom_api_key:
            attom_history = self._get_attom_sales_history(address)
            if attom_history:
                sales_history.extend(attom_history)
        
        return sales_history

    def _get_zillow_sales_history(self, zpid):
        """
        Get sales history from Zillow using property zpid
        
        Args:
            zpid: Zillow property ID
            
        Returns:
            list: Sales history events
        """
        try:
            # Build Zillow Property API URL via RapidAPI
            url = f"https://zillow-com1.p.rapidapi.com/property?zpid={zpid}"
            
            # Make the request
            response = self.session.get(url, headers=self.zillow_headers)
            response.raise_for_status()
            
            # Parse the response
            data = response.json()
            
            if 'priceHistory' in data:
                history = []
                
                for event in data['priceHistory']:
                    history_event = {
                        'date': event.get('date', ''),
                        'price': event.get('price', 0),
                        'event': event.get('event', ''),
                        'source': 'Zillow'
                    }
                    history.append(history_event)
                
                return history
                
            return []
            
        except Exception as e:
            logger.error(f"Error getting Zillow sales history: {str(e)}")
            return []

    def _get_attom_sales_history(self, address):
        """
        Get sales history from ATTOM Data
        
        Args:
            address: The property address
            
        Returns:
            list: Sales history events
        """
        try:
            # Parse the address
            address_parts = address.split(',')
            street_address = address_parts[0].strip()
            
            if len(address_parts) >= 3:
                city = address_parts[1].strip()
                state_zip = address_parts[2].strip().split()
                state = state_zip[0]
                zip_code = state_zip[1] if len(state_zip) > 1 else ""
            else:
                # Format might be incomplete
                logger.warning(f"Address format may be incomplete for ATTOM API: {address}")
                return []
            
            # Build ATTOM API URL
            url = "https://api.gateway.attomdata.com/propertyapi/v1.0.0/saleshistory/detail"
            params = {
                'address1': street_address,
                'address2': f"{city}, {state} {zip_code}"
            }
            
            # Make the request
            response = self.session.get(url, headers=self.attom_headers, params=params)
            response.raise_for_status()
            
            # Parse the response
            data = response.json()
            
            if 'property' in data and data['property']:
                result = data['property'][0]
                
                if 'salehistory' in result:
                    history = []
                    
                    for sale in result['salehistory']:
                        history_event = {
                            'date': sale.get('saledate', ''),
                            'price': sale.get('amount', {}).get('saleamt', 0),
                            'event': 'Sold',
                            'source': 'ATTOM Data'
                        }
                        history.append(history_event)
                    
                    return history
                
            return []
            
        except Exception as e:
            logger.error(f"Error getting ATTOM sales history: {str(e)}")
            return []

    def get_property_value_forecast(self, property_data, years=5):
        """
        Get property value forecast for future years
        
        Args:
            property_data: Current property data
            years: Number of years to forecast
            
        Returns:
            dict: Forecasted values by year
        """
        try:
            if 'estimated_value' not in property_data:
                return None
                
            current_value = property_data['estimated_value']
            forecast = {}
            
            # Get location data for region-specific growth rates
            zip_code = property_data.get('zip', '')
            state = property_data.get('state', '')
            
            # Get region growth rate from HouseCanary if available
            if self.housecanary_api_key and self.housecanary_api_secret:
                growth_rate = self._get_region_growth_rate(zip_code, state)
            else:
                # Use national average if specific data not available
                growth_rate = 0.035  # 3.5% annually
            
            # Generate the forecast
            for year in range(1, years + 1):
                future_value = current_value * ((1 + growth_rate) ** year)
                forecast[year] = int(future_value)
            
            return forecast
            
        except Exception as e:
            logger.error(f"Error generating property value forecast: {str(e)}")
            return None

    def _get_region_growth_rate(self, zip_code, state):
        """
        Get region-specific home value growth rate
        
        Args:
            zip_code: The property ZIP code
            state: The property state
            
        Returns:
            float: Annual growth rate
        """
        try:
            # Build HouseCanary API URL
            url = "https://api.housecanary.com/v2/home_price_trends"
            params = {
                'zipcode': zip_code
            }
            
            # Set up authentication
            auth = (self.housecanary_api_key, self.housecanary_api_secret)
            
            # Make the request
            response = self.session.get(url, params=params, auth=auth)
            response.raise_for_status()
            
            # Parse the response
            data = response.json()
            
            if 'home_price_trends' in data and 'result' in data['home_price_trends']:
                result = data['home_price_trends']['result']
                
                # Get the annual growth rate
                return result.get('annual_growth', 0.035)  # Default to 3.5% if not found
            
            return 0.035  # Default to national average
            
        except Exception as e:
            logger.error(f"Error getting region growth rate: {str(e)}")
            return 0.035  # Default to national average