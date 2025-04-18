"""
Contractor Data Service

This module handles the retrieval of real contractor data using OpenAI API.
It provides functionality to:
- Find contractors by location and service type
- Rate and categorize contractors based on their reviews
- Organize contractors into service tiers (Standard, Professional, Luxury)
- Cache contractor data to minimize API usage

This service uses the OpenAI API to gather real-world data about service providers.
"""

import os
import re
import json
import time
import logging
import requests
from openai import OpenAI
from urllib.parse import quote_plus
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('contractor_data_service')

# Cache for contractor data to minimize repeated API requests
contractor_cache = {}
CACHE_DURATION = timedelta(days=7)  # Cache contractor data for 7 days

# Service tier thresholds based on rating
TIER_THRESHOLDS = {
    'luxury': 4.5,      # 4.5+ stars for Luxury tier
    'professional': 3.5, # 3.5-4.4 stars for Professional tier
    'standard': 3.0     # Around 3 stars for Standard tier
}

class ContractorDataService:
    """Service for fetching contractor data using OpenAI API"""
    
    def __init__(self):
        """Initialize with OpenAI API key"""
        # Get API key from environment
        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            logger.error("OpenAI API key not configured")
            raise ValueError("OpenAI API key is required")
            
        self.api_key = api_key
        
        # Initialize OpenAI client properly without proxies
        # In OpenAI 1.3.0+, the proxies parameter is not supported
        try:
            import httpx
            # Create httpx client explicitly without proxies
            http_client = httpx.Client(timeout=60.0)
            self.openai_client = OpenAI(api_key=api_key, http_client=http_client)
            logger.info("OpenAI client initialized in contractor data service")
        except Exception as e:
            logger.error(f"Error initializing OpenAI client: {str(e)}")
            raise
    
    def get_contractors_by_service_location(self, service_type, city, state, limit=9):
        """
        Get real contractor data for a specific service type and location
        
        Args:
            service_type (str): Type of service (e.g., "Roofing", "Plumbing")
            city (str): City name
            state (str): State name or abbreviation
            limit (int): Maximum number of contractors to return
            
        Returns:
            list: List of contractor dictionaries with details
        """
        # Create cache key
        cache_key = f"{service_type.lower()}_{city.lower()}_{state.lower()}"
        
        # Check cache first
        if cache_key in contractor_cache:
            cache_entry = contractor_cache[cache_key]
            # Check if cache entry is still valid
            if datetime.now() - cache_entry['timestamp'] < CACHE_DURATION:
                logger.info(f"Using cached contractor data for {service_type} in {city}, {state}")
                return cache_entry['data'][:limit]
        
        # Format prompt to ask for contractors
        prompt = self._create_contractor_prompt(service_type, city, state)
        
        try:
            # Call OpenAI API
            logger.info(f"Fetching contractor data for {service_type} in {city}, {state}")
            data = self._query_openai(prompt)
            
            if not data:
                logger.error("No contractor data returned from OpenAI")
                return []
                
            # Process and structure the data
            contractors = self._process_contractor_data(data, service_type, city, state)
            
            # Categorize into tiers based on ratings
            contractors = self._categorize_contractors_by_tier(contractors)
            
            # Cache the results with timestamp
            contractor_cache[cache_key] = {
                'data': contractors,
                'timestamp': datetime.now()
            }
            
            return contractors[:limit]
            
        except Exception as e:
            logger.error(f"Error fetching contractor data: {str(e)}")
            return []
    
    def get_contractors_by_tier(self, service_type, city, state, tier='professional', limit=3):
        """
        Get contractors for a specific service, location and quality tier
        
        Args:
            service_type (str): Type of service (e.g., "Roofing", "Plumbing")
            city (str): City name
            state (str): State name or abbreviation
            tier (str): 'standard', 'professional', or 'luxury'
            limit (int): Maximum number of contractors to return
            
        Returns:
            list: List of contractor dictionaries with details
        """
        # Get all contractors first
        all_contractors = self.get_contractors_by_service_location(service_type, city, state)
        
        # Filter by requested tier
        tier_contractors = [c for c in all_contractors if c.get('tier', '').lower() == tier.lower()]
        
        # If we don't have enough for the requested tier, get from next tier down
        if len(tier_contractors) < limit:
            if tier.lower() == 'luxury':
                # Try professional tier
                tier_contractors.extend([c for c in all_contractors 
                                      if c.get('tier', '').lower() == 'professional'
                                      and c not in tier_contractors])
            elif tier.lower() == 'professional':
                # Try standard tier
                tier_contractors.extend([c for c in all_contractors 
                                      if c.get('tier', '').lower() == 'standard'
                                      and c not in tier_contractors])
            
        return tier_contractors[:limit]
    
    def _create_contractor_prompt(self, service_type, city, state):
        """
        Create a prompt for OpenAI to get contractor information
        
        Args:
            service_type (str): Type of service
            city (str): City name
            state (str): State name
            
        Returns:
            str: Formatted prompt
        """
        return f"""Find the top 9 real, reputable {service_type} contractors in {city}, {state}. 
        Research actual companies that operate in this area using real data about their services, ratings and contact information.
        
        For each contractor, provide the following information in JSON format:
        - Business name (real company name)
        - Address (full address if available)
        - Phone number (actual business phone)
        - Website URL (real website if available)
        - Rating (on scale of 1-5 stars from review sites like Google, Yelp, etc.)
        - Number of reviews
        - Years in business (if available)
        - Services offered (list of specific services within {service_type})
        - Price range ($ to $$$$ scale)
        - Areas served (list of cities/areas)
        - Business hours
        - Special qualifications or certifications
        
        Format the response as a JSON array where each contractor is an object with these fields. 
        These should be real businesses that operate in {city}, {state} that customers could actually contact.
        Do not include any introduction or explanation, just the JSON data."""
    
    def _query_openai(self, prompt):
        """
        Query OpenAI API with the given prompt
        
        Args:
            prompt (str): Prompt to send to OpenAI
            
        Returns:
            dict or list: Parsed JSON data from OpenAI response
        """
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",  # the newest OpenAI model is "gpt-4o" which was released May, 2024
                messages=[
                    {"role": "system", "content": "You are a service that provides accurate, up-to-date information about local contractors and service providers. You accurately report real businesses, real ratings, and real contact information without fabrication."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,  # Low temperature for more factual responses
                max_tokens=2000
            )
            
            # Extract and parse the JSON from the response
            json_str = response.choices[0].message.content.strip()
            
            # Try to clean up the JSON string if it's not properly formatted
            json_str = self._clean_json_string(json_str)
            
            try:
                data = json.loads(json_str)
                return data
            except json.JSONDecodeError as json_err:
                logger.error(f"Error parsing OpenAI response as JSON: {str(json_err)}")
                logger.error(f"Response content: {json_str}")
                return None
                
        except Exception as e:
            logger.error(f"Error querying OpenAI: {str(e)}")
            return None
    
    def _clean_json_string(self, json_str):
        """
        Clean up a JSON string if it's not properly formatted
        
        Args:
            json_str (str): JSON string to clean
            
        Returns:
            str: Cleaned JSON string
        """
        # Remove markdown code blocks if present
        json_str = re.sub(r'^```json\s*', '', json_str)
        json_str = re.sub(r'\s*```$', '', json_str)
        
        # Remove any leading/trailing whitespace
        json_str = json_str.strip()
        
        return json_str
    
    def _process_contractor_data(self, data, service_type, city, state):
        """
        Process and structure contractor data
        
        Args:
            data (list): Raw contractor data from OpenAI
            service_type (str): Type of service
            city (str): City name
            state (str): State name
            
        Returns:
            list: Processed and structured contractor data
        """
        processed_contractors = []
        
        # Ensure data is a list
        if not isinstance(data, list):
            logger.error(f"Expected list but got {type(data)}")
            if isinstance(data, dict):
                # If it's a dict with a list field, try to extract it
                for key, value in data.items():
                    if isinstance(value, list):
                        data = value
                        break
                else:
                    # Convert single dict to list with one item
                    data = [data]
            else:
                return processed_contractors
        
        for contractor in data:
            try:
                # Standardize and enhance the contractor data
                processed = {
                    'name': contractor.get('Business name', contractor.get('name', '')),
                    'address': contractor.get('Address', contractor.get('address', '')),
                    'phone': contractor.get('Phone number', contractor.get('phone', contractor.get('phone_number', ''))),
                    'website': contractor.get('Website URL', contractor.get('website', contractor.get('url', ''))),
                    'rating': float(contractor.get('Rating', contractor.get('rating', 0))),
                    'reviews': int(contractor.get('Number of reviews', contractor.get('reviews', contractor.get('review_count', 0)))),
                    'years_in_business': contractor.get('Years in business', contractor.get('years', contractor.get('years_in_business', 'N/A'))),
                    'services': contractor.get('Services offered', contractor.get('services', [])),
                    'price_range': contractor.get('Price range', contractor.get('price', contractor.get('price_range', '$$$'))),
                    'areas_served': contractor.get('Areas served', contractor.get('areas', [city])),
                    'business_hours': contractor.get('Business hours', contractor.get('hours', 'Mon-Fri: 8AM-5PM')),
                    'certifications': contractor.get('Special qualifications or certifications', contractor.get('certifications', contractor.get('qualifications', []))),
                    'service_type': service_type,
                    'city': city,
                    'state': state,
                    'data_source': 'openai_api'
                }
                
                # Add some default fields if missing
                if not processed['services']:
                    processed['services'] = [service_type]
                
                if not processed['areas_served']:
                    processed['areas_served'] = [city]
                    
                # Add to the processed list
                processed_contractors.append(processed)
                
            except Exception as e:
                logger.error(f"Error processing contractor: {str(e)}")
                continue
        
        return processed_contractors
    
    def _categorize_contractors_by_tier(self, contractors):
        """
        Categorize contractors into quality tiers based on ratings
        
        Args:
            contractors (list): List of contractor dictionaries
            
        Returns:
            list: Contractors with tier field added
        """
        for contractor in contractors:
            rating = float(contractor.get('rating', 0))
            
            # Assign tier based on rating
            if rating >= TIER_THRESHOLDS['luxury']:
                contractor['tier'] = 'luxury'
            elif rating >= TIER_THRESHOLDS['professional']:
                contractor['tier'] = 'professional'
            elif rating >= TIER_THRESHOLDS['standard']:
                contractor['tier'] = 'standard'
            else:
                contractor['tier'] = 'standard'  # Default to standard for low ratings
                
        return contractors

    def get_service_cost_estimate(self, service_type, location, property_details, tier='professional'):
        """
        Get an estimated cost for a specific service type in a location
        
        Args:
            service_type (str): Type of service (e.g., "Roofing", "Plumbing")
            location (dict): Location with city and state
            property_details (dict): Property details including square_feet, bedrooms, etc.
            tier (str): Service tier ('standard', 'professional', or 'luxury')
            
        Returns:
            dict: Cost estimate with price ranges and details
        """
        # Parse location
        city = location.get('city', '')
        state = location.get('state', '')
        
        # Extract property details
        square_feet = property_details.get('square_feet', 2000)
        year_built = property_details.get('year_built', 1990)
        
        # Create cache key
        cache_key = f"cost_{service_type.lower()}_{city.lower()}_{state.lower()}_{square_feet}_{tier}"
        
        # Check cache first
        if cache_key in contractor_cache:
            cache_entry = contractor_cache[cache_key]
            # Check if cache entry is still valid
            if datetime.now() - cache_entry['timestamp'] < CACHE_DURATION:
                logger.info(f"Using cached cost estimate for {service_type} in {city}, {state}")
                return cache_entry['data']
        
        # Create the cost estimate prompt
        prompt = self._create_cost_estimate_prompt(
            service_type, city, state, square_feet, year_built, tier
        )
        
        try:
            # Query OpenAI for cost estimate
            data = self._query_openai(prompt)
            
            if not data:
                logger.error("No cost estimate data returned from OpenAI")
                return {
                    "error": "Failed to get cost estimate",
                    "service_type": service_type,
                    "location": f"{city}, {state}",
                    "tier": tier
                }
            
            # Process and structure the data
            if isinstance(data, list) and len(data) > 0:
                estimate = data[0]
            else:
                estimate = data
            
            # Add some additional context
            estimate['service_type'] = service_type
            estimate['location'] = f"{city}, {state}"
            estimate['tier'] = tier
            estimate['property_size'] = square_feet
            estimate['data_source'] = 'openai_api'
            
            # Cache the results
            contractor_cache[cache_key] = {
                'data': estimate,
                'timestamp': datetime.now()
            }
            
            return estimate
            
        except Exception as e:
            logger.error(f"Error getting cost estimate: {str(e)}")
            return {
                "error": f"Failed to get cost estimate: {str(e)}",
                "service_type": service_type,
                "location": f"{city}, {state}",
                "tier": tier
            }
    
    def get_quote_details(self, service_type, contractor_name, location, property_details, tier='professional'):
        """
        Get detailed quote information for a specific contractor and service
        
        Args:
            service_type (str): Type of service (e.g., "Roofing", "Plumbing")
            contractor_name (str): Name of the contractor
            location (dict): Location dictionary with city and state
            property_details (dict): Property details including square_feet, bedrooms, etc.
            tier (str): Service tier ('standard', 'professional', or 'luxury')
            
        Returns:
            dict: Detailed quote with pricing breakdown and options
        """
        # Parse location
        city = location.get('city', '')
        state = location.get('state', '')
        
        # Extract property details
        square_feet = property_details.get('square_feet', 2000)
        year_built = property_details.get('year_built', 1990)
        bedrooms = property_details.get('bedrooms', 3)
        bathrooms = property_details.get('bathrooms', 2)
        
        # Create cache key
        cache_key = f"quote_{service_type.lower()}_{contractor_name}_{city.lower()}_{state.lower()}_{square_feet}_{tier}"
        
        # Check cache first
        if cache_key in contractor_cache:
            cache_entry = contractor_cache[cache_key]
            # Check if cache entry is still valid
            if datetime.now() - cache_entry['timestamp'] < CACHE_DURATION:
                logger.info(f"Using cached quote for {contractor_name} ({service_type}) in {city}, {state}")
                return cache_entry['data']
        
        # Create the detailed quote prompt
        prompt = self._create_detailed_quote_prompt(
            service_type, contractor_name, city, state, 
            square_feet, year_built, bedrooms, bathrooms, tier
        )
        
        try:
            # Query OpenAI for detailed quote
            data = self._query_openai(prompt)
            
            if not data:
                logger.error("No detailed quote data returned from OpenAI")
                return {
                    "error": "Failed to get detailed quote",
                    "service_type": service_type,
                    "contractor": contractor_name,
                    "location": f"{city}, {state}",
                    "tier": tier
                }
            
            # Process and structure the data
            if isinstance(data, list) and len(data) > 0:
                quote = data[0]
            else:
                quote = data
            
            # Add some additional context
            quote['service_type'] = service_type
            quote['contractor'] = contractor_name
            quote['location'] = f"{city}, {state}"
            quote['tier'] = tier
            quote['property_size'] = square_feet
            quote['data_source'] = 'openai_api'
            
            # Cache the results
            contractor_cache[cache_key] = {
                'data': quote,
                'timestamp': datetime.now()
            }
            
            return quote
            
        except Exception as e:
            logger.error(f"Error getting detailed quote: {str(e)}")
            return {
                "error": f"Failed to get detailed quote: {str(e)}",
                "service_type": service_type,
                "contractor": contractor_name,
                "location": f"{city}, {state}",
                "tier": tier
            }
            
    def _create_cost_estimate_prompt(self, service_type, city, state, square_feet, year_built, tier):
        """
        Create a prompt for OpenAI to get cost estimates for a service
        
        Args:
            service_type (str): Type of service
            city (str): City name
            state (str): State name
            square_feet (int): Square footage of property
            year_built (int): Year property was built
            tier (str): Service tier level
            
        Returns:
            str: Formatted prompt
        """
        tier_descriptions = {
            'standard': 'basic, economical service with standard materials and warranties',
            'professional': 'mid-range service with good quality materials and labor',
            'luxury': 'premium service with top-quality materials and extended warranties'
        }
        
        tier_desc = tier_descriptions.get(tier.lower(), tier_descriptions['professional'])
        
        return f"""Provide a detailed cost estimate for {service_type} service in {city}, {state} for a {square_feet} sq ft property built in {year_built}.
        
        This is for {tier} tier service, which means {tier_desc}.
        
        Format the response as a single JSON object with these fields:
        - price_range: Object with min and max price estimates for this service (numeric values)
        - base_price_per_sqft: Typical price per square foot for this service in this area (if applicable)
        - factors: Array of factors that affect pricing (material costs, labor, permits, etc.)
        - breakdown: Object showing percentage breakdown of costs (materials, labor, permits, overhead)
        - timeline: Typical project timeline in days
        - regional_factor: How the costs in {city}, {state} compare to national average (percentage)
        - notes: Any specific notes about pricing for this service in this area
        
        Provide real, accurate pricing based on current market rates in {city}, {state}. Do not include explanatory text, just the JSON object."""
    
    def _create_detailed_quote_prompt(self, service_type, contractor_name, city, state, 
                                      square_feet, year_built, bedrooms, bathrooms, tier):
        """
        Create a prompt for OpenAI to get a detailed quote from a specific contractor
        
        Args:
            service_type (str): Type of service
            contractor_name (str): Name of contractor
            city (str): City name
            state (str): State name
            square_feet (int): Square footage of property
            year_built (int): Year property was built
            bedrooms (int): Number of bedrooms
            bathrooms (float): Number of bathrooms
            tier (str): Service tier level
            
        Returns:
            str: Formatted prompt
        """
        tier_descriptions = {
            'standard': 'basic, economical service with standard materials and warranties',
            'professional': 'mid-range service with good quality materials and labor',
            'luxury': 'premium service with top-quality materials and extended warranties'
        }
        
        tier_desc = tier_descriptions.get(tier.lower(), tier_descriptions['professional'])
        
        return f"""Create a detailed quote from {contractor_name}, a real {service_type} contractor in {city}, {state}, for a {square_feet} sq ft property built in {year_built} with {bedrooms} bedrooms and {bathrooms} bathrooms.
        
        This quote should be for {tier} tier service, which means {tier_desc}.
        
        Format the response as a JSON object with these fields:
        - contractor_name: The name of the contractor ({contractor_name})
        - total_price: The total estimated price (numeric value)
        - price_range: Object with min and max price (numeric values)
        - line_items: Array of objects with service components and their costs
        - materials: Array of materials to be used with costs
        - timeline: Expected project timeline in days
        - payment_schedule: Object showing payment schedule stages and percentages
        - warranty: Warranty information
        - notes: Any specific notes about this quote
        - options: Array of optional upgrades or additions with prices
        
        Provide a realistic, detailed quote that {contractor_name} might actually offer for this service in {city}, {state}. 
        Do not include explanatory text, just the JSON object."""

# For testing and direct module usage
if __name__ == "__main__":
    service = ContractorDataService()
    
    # Test with a sample service and location
    contractors = service.get_contractors_by_service_location("Roofing", "Saginaw", "Michigan")
    
    # Print the results
    print(json.dumps(contractors, indent=2))
    
    # Test getting contractors by tier
    luxury_contractors = service.get_contractors_by_tier("Roofing", "Saginaw", "Michigan", tier="luxury")
    
    print(f"\nLuxury Tier Contractors ({len(luxury_contractors)}):")
    for c in luxury_contractors:
        print(f"{c['name']} - {c['rating']} stars")
        
    # Test getting cost estimates
    cost_estimate = service.get_service_cost_estimate(
        "Roofing",
        {"city": "Saginaw", "state": "Michigan"},
        {"square_feet": 5000, "year_built": 1995},
        "professional"
    )
    
    print("\nCost Estimate:")
    print(json.dumps(cost_estimate, indent=2))