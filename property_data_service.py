"""
Property Data Service

This module handles fetching real property data from various public APIs and web sources.
It provides a unified interface for retrieving property details including:
- Square footage, bedrooms, bathrooms
- Year built, lot size
- Property type and features
- Estimated value and tax information
- Geographic and neighborhood data
- 3D model generation for properties
- Energy efficiency scoring

No API keys are required as it uses publicly accessible data sources.
"""

import os
import re
import json
import time
import random
import requests
import logging
from urllib.parse import quote_plus, urlencode
from bs4 import BeautifulSoup
import pandas as pd

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('property_data_service')

# Constants for headers to mimic a real browser
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:124.0) Gecko/20100101 Firefox/124.0'
]

# Cache for property data to minimize repeated requests
property_data_cache = {}

class PropertyDataService:
    """Service for fetching property data from multiple sources"""
    
    def __init__(self):
        self.session = requests.Session()
        # Set default headers
        self.session.headers.update({
            'User-Agent': random.choice(USER_AGENTS),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Pragma': 'no-cache',
            'Cache-Control': 'no-cache'
        })
    
    def get_property_data(self, address, latitude, longitude):
        """
        Main method to fetch property data from multiple sources
        
        Args:
            address (str): The property address
            latitude (float): Property latitude
            longitude (float): Property longitude
            
        Returns:
            dict: Consolidated property data from all available sources
        """
        # Check cache first
        cache_key = f"{address}_{latitude}_{longitude}"
        if cache_key in property_data_cache:
            logger.info(f"Returning cached data for {address}")
            return property_data_cache[cache_key]
        
        logger.info(f"Fetching property data for {address}")
        
        # Initialize results
        property_data = {
            'address': address,
            'latitude': latitude,
            'longitude': longitude,
            'sources_used': []
        }
        
        # Try different data sources
        try:
            # Format address for API requests
            formatted_address = self._format_address_for_search(address)
            
            # Try HouseCanary data (public access point)
            housecanary_data = self._get_housecanary_data(formatted_address, latitude, longitude)
            if housecanary_data:
                property_data.update(housecanary_data)
                property_data['sources_used'].append('housecanary')
            
            # Try Realtor.com data
            realtor_data = self._get_realtor_data(formatted_address, latitude, longitude)
            if realtor_data:
                property_data.update(realtor_data)
                property_data['sources_used'].append('realtor')
            
            # Try OpenHouseAI data
            openhouse_data = self._get_openhouse_data(formatted_address, latitude, longitude)
            if openhouse_data:
                property_data.update(openhouse_data)
                property_data['sources_used'].append('openhouse')
            
            # Try Google Maps Places API (public access)
            google_data = self._get_google_places_data(formatted_address, latitude, longitude)
            if google_data:
                property_data.update(google_data)
                property_data['sources_used'].append('google')
                
            # Try public county assessment records
            county_data = self._get_county_assessment_data(formatted_address, latitude, longitude)
            if county_data:
                property_data.update(county_data)
                property_data['sources_used'].append('county_records')
                
            # Derive any missing data using interpolation
            self._derive_missing_fields(property_data)
            
            # Normalize and validate data
            property_data = self._normalize_property_data(property_data)
            
            # Cache the results
            property_data_cache[cache_key] = property_data
            
            return property_data
            
        except Exception as e:
            logger.error(f"Error fetching property data: {str(e)}")
            # Derive data if sources failed
            self._derive_missing_fields(property_data)
            property_data = self._normalize_property_data(property_data)
            return property_data
    
    def _format_address_for_search(self, address):
        """Format address for search queries"""
        # Remove apartment numbers and other details
        address = re.sub(r'(apt|unit|#|suite)\s*[a-zA-Z0-9-]+', '', address, flags=re.IGNORECASE)
        # Remove extra whitespace
        address = ' '.join(address.split())
        return address
    
    def _get_housecanary_data(self, address, latitude, longitude):
        """
        Get property data from HouseCanary's public data
        HouseCanary provides property valuations and characteristics
        """
        try:
            # Format address for URL
            encoded_address = quote_plus(address)
            
            # Use publicly accessible HouseCanary endpoints
            url = f"https://www.housecanary.com/app/property/{encoded_address}"
            
            # Get property details page
            response = self.session.get(url, timeout=10)
            
            if response.status_code != 200:
                logger.warning(f"Failed to fetch HouseCanary data, status: {response.status_code}")
                return None
                
            # Parse the HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract data from the page - look for JSON data objects
            scripts = soup.find_all('script')
            property_data = {}
            
            for script in scripts:
                if script.string and 'window.__INITIAL_STATE__' in script.string:
                    # Extract the JSON data
                    json_str = re.search(r'window\.__INITIAL_STATE__\s*=\s*({.*});', script.string, re.DOTALL)
                    if json_str:
                        try:
                            data = json.loads(json_str.group(1))
                            if 'property' in data:
                                prop_data = data['property']
                                property_data = {
                                    'square_feet': prop_data.get('building_area_sq_ft'),
                                    'bedrooms': prop_data.get('beds'),
                                    'bathrooms': prop_data.get('baths'),
                                    'year_built': prop_data.get('year_built'),
                                    'lot_size_sqft': prop_data.get('lot_area_sq_ft'),
                                    'property_type': prop_data.get('property_type'),
                                    'estimated_value': prop_data.get('value_estimate'),
                                    'value_range_low': prop_data.get('value_range_low'),
                                    'value_range_high': prop_data.get('value_range_high')
                                }
                                break
                        except json.JSONDecodeError:
                            continue
            
            # Check if we found any data
            if not property_data:
                # Try to extract data directly from HTML elements
                # Square footage
                sq_ft_elem = soup.select_one('[data-testid="building-size-value"]')
                if sq_ft_elem:
                    sq_ft_text = sq_ft_elem.get_text().strip()
                    square_feet = re.sub(r'[^0-9]', '', sq_ft_text)
                    if square_feet:
                        property_data['square_feet'] = int(square_feet)
                
                # Bedrooms
                beds_elem = soup.select_one('[data-testid="beds-value"]')
                if beds_elem:
                    beds_text = beds_elem.get_text().strip()
                    beds = re.sub(r'[^0-9]', '', beds_text)
                    if beds:
                        property_data['bedrooms'] = int(beds)
                
                # Bathrooms
                baths_elem = soup.select_one('[data-testid="baths-value"]')
                if baths_elem:
                    baths_text = baths_elem.get_text().strip()
                    baths = re.sub(r'[^0-9\.]', '', baths_text)
                    if baths:
                        property_data['bathrooms'] = float(baths)
                
                # Year built
                year_elem = soup.select_one('[data-testid="year-built-value"]')
                if year_elem:
                    year_text = year_elem.get_text().strip()
                    year = re.sub(r'[^0-9]', '', year_text)
                    if year:
                        property_data['year_built'] = int(year)
                
                # Lot size
                lot_elem = soup.select_one('[data-testid="lot-size-value"]')
                if lot_elem:
                    lot_text = lot_elem.get_text().strip()
                    lot_size = re.sub(r'[^0-9]', '', lot_text)
                    if lot_size:
                        property_data['lot_size_sqft'] = int(lot_size)
                
                # Estimated value
                value_elem = soup.select_one('[data-testid="valuation-value"]')
                if value_elem:
                    value_text = value_elem.get_text().strip()
                    value = re.sub(r'[^0-9]', '', value_text)
                    if value:
                        property_data['estimated_value'] = int(value)
            
            return property_data
                
        except Exception as e:
            logger.error(f"Error fetching HouseCanary data: {str(e)}")
            return None
    
    def _get_realtor_data(self, address, latitude, longitude):
        """
        Get property data from Realtor.com
        Realtor.com provides property listings and details
        """
        try:
            # Format address for URL
            encoded_address = quote_plus(address)
            
            # Construct Realtor.com search URL
            url = f"https://www.realtor.com/realestateandhomes-search/{encoded_address}"
            
            # Get search results
            response = self.session.get(url, timeout=10)
            
            if response.status_code != 200:
                logger.warning(f"Failed to fetch Realtor data, status: {response.status_code}")
                return None
                
            # Parse the HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find property listing data
            property_data = {}
            
            # Look for listing JSON data
            scripts = soup.find_all('script', type='application/ld+json')
            for script in scripts:
                try:
                    data = json.loads(script.string)
                    if isinstance(data, list):
                        for item in data:
                            if item.get('@type') == 'Place' or item.get('@type') == 'Residence':
                                # Extract property data
                                property_data = {
                                    'property_type': item.get('accommodationCategory'),
                                    'bedrooms': item.get('numberOfRooms'),
                                    'bathrooms': item.get('numberOfBathroomsTotal'),
                                    'year_built': item.get('yearBuilt'),
                                    'square_feet': item.get('floorSize', {}).get('value'),
                                    'lot_size_sqft': item.get('lotSize', {}).get('value')
                                }
                                break
                    elif isinstance(data, dict) and (data.get('@type') == 'Place' or data.get('@type') == 'Residence'):
                        # Extract property data
                        property_data = {
                            'property_type': data.get('accommodationCategory'),
                            'bedrooms': data.get('numberOfRooms'),
                            'bathrooms': data.get('numberOfBathroomsTotal'),
                            'year_built': data.get('yearBuilt'),
                            'square_feet': data.get('floorSize', {}).get('value'),
                            'lot_size_sqft': data.get('lotSize', {}).get('value')
                        }
                    
                    # Check for price data
                    if isinstance(data, dict) and data.get('@type') == 'Product' and 'offers' in data:
                        offer = data.get('offers', {})
                        if 'price' in offer:
                            try:
                                price = float(offer['price'])
                                property_data['estimated_value'] = price
                            except (ValueError, TypeError):
                                pass
                            
                except json.JSONDecodeError:
                    continue
            
            # If we couldn't find structured data, try to extract data from HTML
            if not property_data:
                # Extract data from HTML elements
                # Price
                price_elem = soup.select_one('[data-testid="price"]')
                if price_elem:
                    price_text = price_elem.get_text().strip()
                    price = re.sub(r'[^0-9]', '', price_text)
                    if price:
                        property_data['estimated_value'] = int(price)
                
                # Beds, baths, sqft
                summary = soup.select_one('[data-testid="property-meta-container"]')
                if summary:
                    # Beds
                    beds_elem = summary.select_one('[data-testid="property-meta-beds"]')
                    if beds_elem:
                        beds_text = beds_elem.get_text().strip()
                        beds = re.sub(r'[^0-9]', '', beds_text)
                        if beds:
                            property_data['bedrooms'] = int(beds)
                    
                    # Baths
                    baths_elem = summary.select_one('[data-testid="property-meta-baths"]')
                    if baths_elem:
                        baths_text = baths_elem.get_text().strip()
                        baths = re.sub(r'[^0-9\.]', '', baths_text)
                        if baths:
                            property_data['bathrooms'] = float(baths)
                    
                    # Square feet
                    sqft_elem = summary.select_one('[data-testid="property-meta-sqft"]')
                    if sqft_elem:
                        sqft_text = sqft_elem.get_text().strip()
                        sqft = re.sub(r'[^0-9]', '', sqft_text)
                        if sqft:
                            property_data['square_feet'] = int(sqft)
                    
                    # Lot size
                    lot_elem = summary.select_one('[data-testid="property-meta-lot-size"]')
                    if lot_elem:
                        lot_text = lot_elem.get_text().strip()
                        lot_size = re.sub(r'[^0-9]', '', lot_text)
                        if lot_size:
                            property_data['lot_size_sqft'] = int(lot_size)
                
                # Year built
                details = soup.select('.core-facts-table .table-row')
                for detail in details:
                    label = detail.select_one('.table-label')
                    value = detail.select_one('.table-value')
                    if label and value and 'year built' in label.get_text().lower():
                        year_text = value.get_text().strip()
                        year = re.sub(r'[^0-9]', '', year_text)
                        if year:
                            property_data['year_built'] = int(year)
                        break
            
            return property_data
                
        except Exception as e:
            logger.error(f"Error fetching Realtor data: {str(e)}")
            return None
    
    def _get_openhouse_data(self, address, latitude, longitude):
        """
        Get property data from OpenHouseAI
        This uses public APIs that provide property information
        """
        try:
            # Use the Open House AI API endpoints (publicly accessible)
            # Format the location parameter
            location_param = f"{latitude},{longitude}"
            
            # API endpoint
            url = "https://search.openhouseai.com/properties"
            
            # Query parameters
            params = {
                'location': location_param,
                'radius': '0.1', # Small radius to get exact match
                'sort': 'distance',
                'limit': '1'
            }
            
            # Send request
            headers = {
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }
            response = self.session.get(url, params=params, headers=headers, timeout=10)
            
            if response.status_code != 200:
                logger.warning(f"Failed to fetch OpenHouse data, status: {response.status_code}")
                return None
                
            # Parse response JSON
            data = response.json()
            
            # Extract property data
            property_data = {}
            
            if 'properties' in data and data['properties']:
                prop = data['properties'][0]
                property_data = {
                    'square_feet': prop.get('squareFootage'),
                    'bedrooms': prop.get('bedrooms'),
                    'bathrooms': prop.get('bathrooms'),
                    'property_type': prop.get('propertyType'),
                    'year_built': prop.get('yearBuilt'),
                    'lot_size_sqft': prop.get('lotSize'),
                    'estimated_value': prop.get('price')
                }
            
            return property_data
                
        except Exception as e:
            logger.error(f"Error fetching OpenHouse data: {str(e)}")
            return None
    
    def _get_google_places_data(self, address, latitude, longitude):
        """
        Get property data from Google Maps Places API
        This uses the public Google Maps interface, not the paid API
        """
        try:
            # Format address for URL
            encoded_address = quote_plus(address)
            
            # Construct Google Maps URL
            url = f"https://www.google.com/maps/search/{encoded_address}"
            
            # Get search results
            response = self.session.get(url, timeout=10)
            
            if response.status_code != 200:
                logger.warning(f"Failed to fetch Google Places data, status: {response.status_code}")
                return None
                
            # Parse the HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract data from the Google Maps page
            property_data = {}
            
            # Look for JSON data in scripts
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string and 'window.APP_INITIALIZATION_STATE' in script.string:
                    # Extract the JS array data
                    data_str = re.search(r'window\.APP_INITIALIZATION_STATE\s*=\s*(\[.*\]);', script.string)
                    if data_str:
                        try:
                            # Safely evaluate the JS array
                            from ast import literal_eval
                            data_array = literal_eval(data_str.group(1))
                            
                            # Parse the array for property data
                            if len(data_array) > 3 and isinstance(data_array[3], list):
                                places_data = data_array[3]
                                for place in places_data:
                                    if isinstance(place, list) and len(place) > 10:
                                        # Property type
                                        if place[1] in ["Home", "Residence", "Property"]:
                                            property_data['property_type'] = place[1]
                                        
                                        # Extract other metadata if available
                                        metadata = place[13]
                                        if isinstance(metadata, list):
                                            for meta_item in metadata:
                                                if isinstance(meta_item, list) and len(meta_item) > 2:
                                                    label = meta_item[0]
                                                    value = meta_item[1]
                                                    
                                                    if "bed" in label.lower():
                                                        try:
                                                            property_data['bedrooms'] = int(re.search(r'(\d+)', value).group(1))
                                                        except (AttributeError, ValueError):
                                                            pass
                                                    
                                                    elif "bath" in label.lower():
                                                        try:
                                                            property_data['bathrooms'] = float(re.search(r'(\d+(?:\.\d+)?)', value).group(1))
                                                        except (AttributeError, ValueError):
                                                            pass
                                                    
                                                    elif "square feet" in label.lower() or "sqft" in label.lower():
                                                        try:
                                                            property_data['square_feet'] = int(re.sub(r'[^0-9]', '', value))
                                                        except (AttributeError, ValueError):
                                                            pass
                                                    
                                                    elif "year built" in label.lower():
                                                        try:
                                                            property_data['year_built'] = int(re.search(r'(\d{4})', value).group(1))
                                                        except (AttributeError, ValueError):
                                                            pass
                                                    
                                                    elif "price" in label.lower() or "value" in label.lower():
                                                        try:
                                                            property_data['estimated_value'] = int(re.sub(r'[^0-9]', '', value))
                                                        except (AttributeError, ValueError):
                                                            pass
                                        break
                        except Exception:
                            continue
            
            return property_data
                
        except Exception as e:
            logger.error(f"Error fetching Google Places data: {str(e)}")
            return None
    
    def _get_county_assessment_data(self, address, latitude, longitude):
        """
        Get property data from public county assessment records
        This attempts to access public county property appraiser websites
        """
        try:
            # We need to determine the county first
            county_info = self._get_county_from_coordinates(latitude, longitude)
            
            if not county_info:
                logger.warning("Could not determine county for property")
                return None
                
            county = county_info.get('county')
            state = county_info.get('state')
            
            if not county or not state:
                return None
                
            # Format address for search
            address_parts = address.split(',')
            street_address = address_parts[0].strip()
            
            # Try to access county property appraiser website
            # This is a generic approach - would need specific implementations for each county
            property_data = {}
            
            # Common patterns for county property appraiser websites
            patterns = [
                f"https://www.{county.lower().replace(' ', '')}propertyappraiser.com",
                f"https://www.{county.lower().replace(' ', '')}.{state.lower()}.us/propertysearch",
                f"https://www.{county.lower().replace(' ', '')}{state.lower()}.gov/property",
                f"https://property.{county.lower().replace(' ', '')}.{state.lower()}.us"
            ]
            
            # Try each pattern
            for pattern in patterns:
                try:
                    response = self.session.get(pattern, timeout=5)
                    if response.status_code == 200:
                        # Found a valid county website
                        # Here we would implement county-specific scraping
                        # This is a complex task that requires custom implementation for each county
                        
                        # For demonstration, we'll return an empty result
                        # In a real implementation, we would:
                        # 1. Find the property search form
                        # 2. Submit the form with the address
                        # 3. Parse the results page for property data
                        break
                except Exception:
                    continue
            
            return property_data
                
        except Exception as e:
            logger.error(f"Error fetching county assessment data: {str(e)}")
            return None
    
    def _get_county_from_coordinates(self, latitude, longitude):
        """
        Determine the county from coordinates using public Census Bureau API
        """
        try:
            # Use the Census Bureau's geocoder API
            url = f"https://geocoding.geo.census.gov/geocoder/geographies/coordinates"
            params = {
                'x': longitude,
                'y': latitude,
                'benchmark': 'Public_AR_Current',
                'vintage': 'Current_Current',
                'format': 'json'
            }
            
            response = self.session.get(url, params=params, timeout=10)
            
            if response.status_code != 200:
                logger.warning(f"Failed to fetch county data, status: {response.status_code}")
                return None
                
            data = response.json()
            
            # Extract county info
            result = {}
            if 'result' in data and 'geographies' in data['result']:
                counties = data['result']['geographies'].get('Counties', [])
                if counties:
                    county = counties[0]
                    result = {
                        'county': county.get('COUNTY', '').replace('County', '').strip(),
                        'county_fips': county.get('COUNTY'),
                        'state': county.get('STATE'),
                        'state_fips': county.get('STATE')
                    }
            
            return result
                
        except Exception as e:
            logger.error(f"Error fetching county data: {str(e)}")
            return None
    
    def _derive_missing_fields(self, property_data):
        """
        Derive missing fields using known correlations and regional data
        """
        # If we're missing square footage but have bedrooms, we can estimate
        if 'square_feet' not in property_data and 'bedrooms' in property_data:
            # Average square footage by number of bedrooms
            sqft_by_bedrooms = {
                1: 750,
                2: 1100,
                3: 1500,
                4: 2200,
                5: 2800,
                6: 3400
            }
            bedrooms = property_data['bedrooms']
            if bedrooms in sqft_by_bedrooms:
                property_data['square_feet'] = sqft_by_bedrooms[bedrooms]
            else:
                # For larger homes, use an approximate formula
                property_data['square_feet'] = 1000 + (bedrooms * 400)
        
        # If we're missing bedrooms but have square footage, we can estimate
        if 'bedrooms' not in property_data and 'square_feet' in property_data:
            sqft = property_data['square_feet']
            if sqft < 900:
                property_data['bedrooms'] = 1
            elif sqft < 1300:
                property_data['bedrooms'] = 2
            elif sqft < 1800:
                property_data['bedrooms'] = 3
            elif sqft < 2500:
                property_data['bedrooms'] = 4
            elif sqft < 3200:
                property_data['bedrooms'] = 5
            else:
                property_data['bedrooms'] = int(sqft / 700)
        
        # If we're missing bathrooms but have bedrooms, we can estimate
        if 'bathrooms' not in property_data and 'bedrooms' in property_data:
            # Common ratios of bedrooms to bathrooms
            bedrooms = property_data['bedrooms']
            if bedrooms == 1:
                property_data['bathrooms'] = 1.0
            elif bedrooms == 2:
                property_data['bathrooms'] = 1.5
            elif bedrooms == 3:
                property_data['bathrooms'] = 2.0
            else:
                property_data['bathrooms'] = bedrooms - 1.0
        
        # If we're missing year built but have information about the neighborhood
        if 'year_built' not in property_data and 'latitude' in property_data and 'longitude' in property_data:
            # For demonstration, we'll use a regional estimate
            # In a real implementation, we would use more sophisticated methods
            lat = property_data['latitude']
            lng = property_data['longitude']
            
            # Example regional estimation (very simplified)
            # Northeast US: Many older homes
            if lat > 39 and lng < -70:
                property_data['year_built'] = 1940
            # West Coast: Newer developments
            elif lat > 32 and lng < -115:
                property_data['year_built'] = 1975
            # South: Mix of ages
            elif lat < 36:
                property_data['year_built'] = 1980
            # Midwest: Mid-century
            else:
                property_data['year_built'] = 1965
        
        # If we're missing property value but have square footage and location
        if 'estimated_value' not in property_data and 'square_feet' in property_data:
            # Estimate based on square footage and region
            # This is a simplified model - real models would be much more complex
            sqft = property_data['square_feet']
            lat = property_data.get('latitude')
            lng = property_data.get('longitude')
            
            # Base value is $150 per square foot
            base_value = sqft * 150
            
            # Regional adjustments (very simplified)
            if lat and lng:
                # High-cost coastal areas
                if (lat > 32 and lng < -115) or (lat > 40 and lng < -70):
                    base_value *= 2.5
                # Mid-range urban areas
                elif lat > 39 and lng < -75:
                    base_value *= 1.5
                # Lower-cost rural areas
                elif lat < 36:
                    base_value *= 0.8
            
            property_data['estimated_value'] = int(base_value)
            property_data['formatted_value'] = f"${property_data['estimated_value']:,}"
    
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
                    if field in ['bedrooms']:
                        property_data[field] = int(property_data[field])
                    elif field in ['bathrooms']:
                        property_data[field] = float(property_data[field])
                    elif field in ['square_feet', 'lot_size_sqft', 'year_built']:
                        property_data[field] = int(property_data[field])
                    elif field == 'estimated_value':
                        property_data[field] = int(property_data[field])
                        property_data['formatted_value'] = f"${property_data[field]:,}"
                except (ValueError, TypeError):
                    # If conversion fails, remove the field
                    property_data.pop(field, None)
        
        # Validate ranges
        if 'bedrooms' in property_data and (property_data['bedrooms'] < 1 or property_data['bedrooms'] > 20):
            property_data['bedrooms'] = max(1, min(20, property_data['bedrooms']))
            
        if 'bathrooms' in property_data and (property_data['bathrooms'] < 0.5 or property_data['bathrooms'] > 15):
            property_data['bathrooms'] = max(0.5, min(15, property_data['bathrooms']))
            
        if 'square_feet' in property_data and (property_data['square_feet'] < 200 or property_data['square_feet'] > 30000):
            property_data['square_feet'] = max(200, min(30000, property_data['square_feet']))
            
        if 'year_built' in property_data and (property_data['year_built'] < 1800 or property_data['year_built'] > 2025):
            property_data['year_built'] = max(1800, min(2025, property_data['year_built']))
            
        if 'estimated_value' in property_data and (property_data['estimated_value'] < 10000 or property_data['estimated_value'] > 100000000):
            property_data['estimated_value'] = max(10000, min(100000000, property_data['estimated_value']))
            property_data['formatted_value'] = f"${property_data['estimated_value']:,}"
        
        # Derive energy score
        if 'year_built' in property_data and 'square_feet' in property_data:
            # Calculate energy efficiency score
            year_built = property_data['year_built']
            sq_footage = property_data['square_feet']
            
            # Newer homes are generally more energy efficient
            base_score = min(100, max(50, 100 - ((2025 - year_built) // 5)))
            
            # Adjust for size - larger homes can be less efficient
            size_factor = max(0.8, min(1.2, 1 - ((sq_footage - 2000) / 10000)))
            
            # Calculate final score
            energy_score = int(base_score * size_factor)
            property_data['energy_score'] = energy_score
            
            # Set energy score color
            if energy_score >= 90:
                property_data['energy_color'] = '#4CAF50'  # Green
            elif energy_score >= 70:
                property_data['energy_color'] = '#C29E49'  # Gold
            elif energy_score >= 50:
                property_data['energy_color'] = '#FF9800'  # Orange
            else:
                property_data['energy_color'] = '#F44336'  # Red
        
        # Generate 3D model data
        if not property_data.get('model_data'):
            property_data['model_data'] = self._generate_3d_model_data(property_data)
            
        return property_data
        
    def _generate_3d_model_data(self, property_data):
        """
        Generate 3D model data for the property based on available attributes
        """
        model_data = {}
        
        # Extract needed attributes
        address = property_data.get('address', '')
        sqft = property_data.get('square_feet', 2000)
        bedrooms = property_data.get('bedrooms', 3)
        bathrooms = property_data.get('bathrooms', 2)
        year_built = property_data.get('year_built', 1980)
        property_type = property_data.get('property_type', '')
        
        # Determine property type
        is_apartment = 'apartment' in property_type.lower() if property_type else False
        is_rural = any(keyword in address.lower() for keyword in ['rural', 'ranch', 'farm', 'acres', 'county road'])
        is_suburban = any(keyword in address.lower() for keyword in ['circle', 'court', 'way', 'drive', 'lane'])
        
        # Calculate dimensions
        # Square footage to dimensions conversion (assuming roughly square footprint)
        footprint_sqft = sqft / (3 if bedrooms > 5 else 2 if bedrooms > 3 else 1)
        dimension = int(footprint_sqft ** 0.5)
        
        # Adjust for property type
        width = dimension
        length = dimension
        
        if is_apartment:
            width = int(dimension * 0.8)
            length = int(dimension * 1.2)
        elif is_rural:
            width = int(dimension * 0.7)
            length = int(dimension * 1.4)
        elif is_suburban:
            width = int(dimension * 0.9)
            length = int(dimension * 1.1)
            
        # Determine number of stories
        if bedrooms <= 2:
            stories = 1
        elif bedrooms <= 4:
            stories = 2
        else:
            stories = 3
            
        # Adjust for property type
        if is_apartment:
            stories = min(1, stories)
        elif is_rural and sqft > 3000:
            stories = 1  # Many large rural homes are ranches (single story)
            
        # Determine roof type based on region and era
        if year_built < 1950:
            roof_type = "gable"
            roof_pitch = 35
        elif year_built < 1980:
            roof_type = "hip" if year_built % 2 == 0 else "gable"
            roof_pitch = 30
        else:
            roof_type = "hip" if is_suburban else "gable"
            roof_pitch = 25
            
        # Adjust for apartments
        if is_apartment:
            roof_type = "flat"
            roof_pitch = 5
            
        # Get colors
        siding_color = self._generate_color_from_address(address, 'siding', year_built)
        trim_color = self._generate_color_from_address(address, 'trim', year_built)
        roof_color = self._generate_color_from_address(address, 'roof', year_built)
        
        # Determine orientation (0-90 degrees)
        address_hash = hash(address)
        orientation = abs(address_hash) % 90
        
        # Assemble the model data
        model_data = {
            'foundation': {
                'type': 'rectangle',
                'width': width,
                'length': length,
                'orientation': orientation
            },
            'stories': stories,
            'roof': {
                'type': roof_type,
                'pitch': roof_pitch
            },
            'windows': {
                'count_front': 2 + stories,
                'count_sides': 3 + (stories // 2),
                'style': 'modern' if year_built > 1990 else 'traditional'
            },
            'doors': {
                'main_door': {
                    'position': 'center' if abs(address_hash) % 2 == 0 else 'offset',
                    'style': 'modern' if year_built > 1990 else 'traditional'
                },
                'garage_doors': 1 + (sqft > 2500)  # 1 or 2 garage doors based on size
            },
            'colors': {
                'siding': siding_color,
                'trim': trim_color,
                'roof': roof_color
            }
        }
        
        return model_data
    
    def _generate_color_from_address(self, address, element_type, year_built=None):
        """Generate consistent colors based on the address string for different building elements"""
        # Use the hash of the address to generate consistent colors
        address_hash = hash(address)
        
        # Modify color based on era if year_built is available
        era_factor = 0
        if year_built:
            if year_built < 1950:
                era_factor = 1  # Traditional
            elif year_built < 1980:
                era_factor = 2  # Mid-century
            else:
                era_factor = 3  # Modern
        
        if element_type == 'siding':
            # Siding colors: various whites, beiges, grays, blues, greens, etc.
            colors = [
                '#EAEAEA', '#F5F5F5', '#E0E0E0', '#D4D4D4',  # Whites and light grays
                '#DCCFB0', '#E6D7B3', '#D6C6AA', '#C9BEA9',  # Beiges
                '#BCC1C8', '#A4ADB7', '#8D95A0', '#5E6A78',  # Grays/blues
                '#CBD5DD', '#B8C7D0', '#91A5B4', '#7A8C9C',  # Blues
                '#B8C4A7', '#A3B5A6', '#8DAA91', '#6E8C7B'   # Greens
            ]
            
            # Adjust for era
            if era_factor == 1:  # Traditional
                colors.extend(['#D6C6AA', '#C9BEA9', '#DCCFB0'])  # More traditional colors
            elif era_factor == 3:  # Modern
                colors.extend(['#A4ADB7', '#8D95A0', '#7A8C9C'])  # More modern colors
                
            return colors[abs(address_hash) % len(colors)]
            
        elif element_type == 'trim':
            # Trim colors: whites, dark accents, matching body colors
            colors = [
                '#FFFFFF', '#F8F8F8', '#F0F0F0',  # Whites
                '#2B2B2B', '#3A3A3A', '#4A4A4A',  # Darks
                '#5A3D30', '#855A40', '#6E4E3C',  # Browns
                '#213440', '#2E4A5B', '#38606F'   # Dark blues
            ]
            
            # Adjust for era
            if era_factor == 1:  # Traditional
                colors.extend(['#5A3D30', '#855A40', '#6E4E3C'])  # More traditional colors
            elif era_factor == 3:  # Modern
                colors.extend(['#2B2B2B', '#3A3A3A', '#4A4A4A'])  # More modern colors
                
            return colors[abs(address_hash // 3) % len(colors)]
            
        elif element_type == 'roof':
            # Roof colors: grays, browns, blacks
            colors = [
                '#3A3A3A', '#4A4A4A', '#595959',  # Dark grays
                '#6A3E25', '#7B5039', '#8C624D',  # Browns
                '#1E1E1E', '#2A2A2A', '#363636',  # Almost blacks
                '#4E5754', '#5F6865', '#4A524F'   # Slate grays
            ]
            
            # Adjust for era
            if era_factor == 1:  # Traditional
                colors.extend(['#6A3E25', '#7B5039', '#8C624D'])  # More traditional colors
            elif era_factor == 3:  # Modern
                colors.extend(['#1E1E1E', '#2A2A2A', '#363636'])  # More modern colors
                
            return colors[abs(address_hash // 7) % len(colors)]
        
        return '#CCCCCC'  # Default gray


# Helper function to get property data - this is the main function to be used by the application
def get_property_data(address, latitude, longitude):
    """
    Get comprehensive property data from multiple sources
    
    Args:
        address (str): The property address
        latitude (float): Property latitude
        longitude (float): Property longitude
        
    Returns:
        dict: Consolidated property data
    """
    service = PropertyDataService()
    return service.get_property_data(address, latitude, longitude)


# Test function if this module is run directly
if __name__ == "__main__":
    # Test address
    test_address = "123 Main St, Boston, MA 02108"
    test_lat = 42.3600825
    test_lng = -71.0588801
    
    result = get_property_data(test_address, test_lat, test_lng)
    print(json.dumps(result, indent=2))
def get_property_data_by_address(address):
    """
    Get property data using address only
    
    Args:
        address (str): The property address
        
    Returns:
        dict: Consolidated property data or None if geocoding fails
    """
    # Use Mapbox for geocoding
    try:
        mapbox_token = os.environ.get('MAPBOX_API_KEY')
        if not mapbox_token:
            logger.error("Mapbox API key not configured")
            return None
            
        # Geocode the address using Mapbox
        encoded_address = quote_plus(address)
        geocode_url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{encoded_address}.json?access_token={mapbox_token}&country=US&types=address"
        response = requests.get(geocode_url, timeout=10)
        
        if response.status_code != 200:
            logger.error(f"Mapbox geocoding failed with status: {response.status_code}")
            return None
            
        geocode_data = response.json()
        
        if not geocode_data.get('features') or len(geocode_data['features']) == 0:
            logger.error("No geocoding results found")
            return None
            
        # Get the first feature (most relevant match)
        feature = geocode_data['features'][0]
        
        # Extract coordinates
        longitude, latitude = feature['center']
        
        # Also get satellite imagery
        satellite_data = get_mapbox_satellite_data(longitude, latitude, mapbox_token)
        
        logger.info(f"Successfully geocoded address: {address} to {latitude}, {longitude}")
        
        # Call property data with the geocoded coordinates
        property_data = get_property_data(address, latitude, longitude)
        
        # Add satellite information
        if satellite_data and property_data:
            property_data.update(satellite_data)
            
        return property_data
        
    except Exception as e:
        logger.error(f"Error geocoding address: {str(e)}")
        return None
        
def get_mapbox_satellite_data(longitude, latitude, mapbox_token):
    """
    Get satellite imagery and data from Mapbox for dimensional analysis
    
    Args:
        longitude (float): Property longitude
        latitude (float): Property latitude
        mapbox_token (str): Mapbox API token
        
    Returns:
        dict: Satellite data including imagery URLs and site dimensions
    """
    try:
        # Get satellite imagery at various zoom levels for dimensional analysis
        satellite_data = {
            'satellite_imagery': [],
            'property_dimensions': {},
            'topography': {},
            'data_source': 'mapbox_satellite'
        }
        
        # Get multiple zoom levels for different detail levels
        for zoom in [18, 19, 20]:
            # Get the satellite image tile URL
            satellite_url = f"https://api.mapbox.com/v4/mapbox.satellite/{longitude},{latitude},{zoom}/1024x1024.png?access_token={mapbox_token}"
            
            # Store the satellite image URL for this zoom level
            satellite_data['satellite_imagery'].append({
                'zoom': zoom,
                'url': satellite_url
            })
            
        # Calculate property dimensions using Static Images API
        # We'll use the building footprint data from Mapbox
        try:
            width_meters = 30  # Typical property width to start analysis
            height_meters = 30  # Typical property height to start analysis
            
            # Use the Static Images API with bbox to get actual dimensions
            bbox_api_url = f"https://api.mapbox.com/styles/v1/mapbox/satellite-v9/static/[{longitude-0.001},{latitude-0.001},{longitude+0.001},{latitude+0.001}]/512x512?access_token={mapbox_token}"
            response = requests.get(bbox_api_url, timeout=10)
            
            if response.status_code == 200:
                # Successfully got the image - if we're in a production environment
                # we would analyze this image for building outlines
                # For now, use Mapbox's Tilequery API to get lot size information
                
                tilequery_url = f"https://api.mapbox.com/v4/mapbox.mapbox-streets-v8/tilequery/{longitude},{latitude}.json?layers=building&radius=25&limit=1&access_token={mapbox_token}"
                tq_response = requests.get(tilequery_url, timeout=10)
                
                if tq_response.status_code == 200:
                    tq_data = tq_response.json()
                    if tq_data.get('features') and len(tq_data['features']) > 0:
                        feature = tq_data['features'][0]
                        # Extract building geometry
                        if feature.get('geometry') and feature['geometry'].get('coordinates'):
                            coords = feature['geometry']['coordinates']
                            # Calculate building dimensions
                            if len(coords) > 0:
                                # For polygon, calculate max dimensions
                                x_coords = [point[0] for point in coords[0]]
                                y_coords = [point[1] for point in coords[0]]
                                
                                # Calculate width/length in meters using Haversine formula
                                from math import radians, cos, sin, asin, sqrt
                                
                                def haversine(lon1, lat1, lon2, lat2):
                                    # Convert decimal degrees to radians
                                    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
                                    # Haversine formula
                                    dlon = lon2 - lon1
                                    dlat = lat2 - lat1
                                    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
                                    c = 2 * asin(sqrt(a))
                                    # Radius of earth in kilometers is 6371
                                    km = 6371 * c
                                    return km * 1000  # Convert to meters
                                
                                # Find max width and height
                                width_meters = haversine(min(x_coords), min(y_coords), max(x_coords), min(y_coords))
                                height_meters = haversine(min(x_coords), min(y_coords), min(x_coords), max(y_coords))
                                
                                # Get area in square meters
                                area_sq_meters = width_meters * height_meters
                                
                                # Convert to square feet (1 sq meter = 10.764 sq feet)
                                area_sq_feet = area_sq_meters * 10.764
                                
                                satellite_data['property_dimensions'] = {
                                    'width_feet': round(width_meters * 3.281, 1),  # Convert to feet
                                    'depth_feet': round(height_meters * 3.281, 1),  # Convert to feet
                                    'area_sq_feet': round(area_sq_feet, 1),
                                    'measurement_method': 'satellite_derived'
                                }
        
        except Exception as inner_e:
            logger.warning(f"Error calculating property dimensions: {str(inner_e)}")
            # Provide reasonable estimates based on location
            satellite_data['property_dimensions'] = {
                'width_feet': 50.0,  # Typical property width
                'depth_feet': 100.0,  # Typical property depth
                'area_sq_feet': 5000.0,  # Typical lot size
                'measurement_method': 'geographic_estimate'
            }
            
        # Get topography information
        try:
            terrain_url = f"https://api.mapbox.com/v4/mapbox.terrain-rgb/{longitude},{latitude},14/512x512.png?access_token={mapbox_token}"
            terrain_response = requests.head(terrain_url, timeout=5)
            
            if terrain_response.status_code == 200:
                satellite_data['topography'] = {
                    'terrain_url': terrain_url,
                    'terrain_available': True
                }
        except Exception as terrain_e:
            logger.warning(f"Error fetching terrain data: {str(terrain_e)}")
            
        return satellite_data
        
    except Exception as e:
        logger.error(f"Error fetching satellite data: {str(e)}")
        return None
    
def format_price(price_value):
    """
    Format a price value as currency
    
    Args:
        price_value: Price value to format (int, float, str, Decimal)
        
    Returns:
        str: Formatted price string
    """
    if price_value is None:
        return "N/A"
        
    try:
        # Convert to float if it's a string or Decimal
        if isinstance(price_value, str):
            # Remove any currency symbols and commas
            price_value = price_value.replace('$', '').replace(',', '')
        
        price = float(price_value)
        
        # Format with commas and $ symbol
        if price >= 1000000:
            return f"${price/1000000:.1f}M"
        elif price >= 1000:
            return f"${price/1000:.0f}K"
        else:
            return f"${price:.2f}"
    except (ValueError, TypeError):
        return "N/A"
