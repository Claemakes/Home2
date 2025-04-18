"""
Enhanced Weather Integration Module for GlassRain

This module provides weather-based maintenance recommendations for properties.
"""

import os
import json
import logging
import datetime
from typing import Dict, List, Any, Optional

import requests
from flask import Blueprint, request, jsonify

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Check if OpenWeather API key is available
openweather_api_key = os.environ.get('OPENWEATHER_API_KEY')
if not openweather_api_key:
    logger.warning("OPENWEATHER_API_KEY environment variable not found. Weather features will use fallback data.")

# Blueprint for Weather Integration routes
weather_bp = Blueprint('weather', __name__)

class WeatherIntegration:
    """
    Enhanced weather integration for property maintenance recommendations
    """
    
    def __init__(self):
        self.api_key = os.environ.get('OPENWEATHER_API_KEY')
        self.has_valid_api = self.api_key is not None
    
    def get_current_weather(self, latitude: float, longitude: float) -> Dict[str, Any]:
        """
        Get current weather data for coordinates
        
        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            
        Returns:
            Dictionary with current weather data
        """
        logger.info(f"Getting current weather for coordinates: {latitude}, {longitude}")
        
        if not self.has_valid_api:
            logger.error("OpenWeather API key is required but not provided")
            raise ValueError("OpenWeather API key is required - please configure OPENWEATHER_API_KEY environment variable")
        
        try:
            # Send request to OpenWeatherMap API
            url = f"https://api.openweathermap.org/data/2.5/weather?lat={latitude}&lon={longitude}&units=imperial&appid={self.api_key}"
            response = requests.get(url)
            
            if response.status_code == 200:
                data = response.json()
                
                # Process weather data
                weather = {
                    'coordinates': {
                        'latitude': latitude,
                        'longitude': longitude
                    },
                    'temperature': {
                        'current': data.get('main', {}).get('temp'),
                        'feels_like': data.get('main', {}).get('feels_like'),
                        'min': data.get('main', {}).get('temp_min'),
                        'max': data.get('main', {}).get('temp_max')
                    },
                    'humidity': data.get('main', {}).get('humidity'),
                    'pressure': data.get('main', {}).get('pressure'),
                    'wind': {
                        'speed': data.get('wind', {}).get('speed'),
                        'direction': data.get('wind', {}).get('deg')
                    },
                    'clouds': data.get('clouds', {}).get('all'),
                    'weather': {
                        'id': data.get('weather', [{}])[0].get('id'),
                        'main': data.get('weather', [{}])[0].get('main'),
                        'description': data.get('weather', [{}])[0].get('description'),
                        'icon': data.get('weather', [{}])[0].get('icon')
                    },
                    'timestamp': data.get('dt'),
                    'location': {
                        'name': data.get('name'),
                        'country': data.get('sys', {}).get('country')
                    },
                    'sunrise': data.get('sys', {}).get('sunrise'),
                    'sunset': data.get('sys', {}).get('sunset'),
                    'timezone': data.get('timezone')
                }
                
                return weather
            else:
                logger.error(f"OpenWeatherMap API error: {response.status_code} - {response.text}")
                raise ValueError(f"OpenWeatherMap API error: {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.error(f"Error getting weather data: {str(e)}")
            raise ValueError(f"Weather data retrieval failed: {str(e)}")
    
    def get_forecast(self, latitude: float, longitude: float, days: int = 5) -> Dict[str, Any]:
        """
        Get weather forecast for coordinates
        
        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            days: Number of days to forecast (max 5)
            
        Returns:
            Dictionary with forecast data
        """
        logger.info(f"Getting forecast for coordinates: {latitude}, {longitude}")
        
        if not self.has_valid_api:
            logger.error("OpenWeather API key is required but not provided")
            raise ValueError("OpenWeather API key is required - please configure OPENWEATHER_API_KEY environment variable")
        
        try:
            # Send request to OpenWeatherMap API (5-day/3-hour forecast)
            url = f"https://api.openweathermap.org/data/2.5/forecast?lat={latitude}&lon={longitude}&units=imperial&appid={self.api_key}"
            response = requests.get(url)
            
            if response.status_code == 200:
                data = response.json()
                
                # Process forecast data
                forecast_items = data.get('list', [])
                
                # Group by day
                daily_forecasts = {}
                for item in forecast_items:
                    # Convert timestamp to date
                    dt = datetime.datetime.fromtimestamp(item.get('dt'))
                    date_key = dt.strftime('%Y-%m-%d')
                    
                    # Initialize day if not exists
                    if date_key not in daily_forecasts:
                        daily_forecasts[date_key] = {
                            'date': date_key,
                            'day_of_week': dt.strftime('%A'),
                            'temperature': {
                                'min': float('inf'),
                                'max': float('-inf'),
                                'average': 0
                            },
                            'humidity': {
                                'min': float('inf'),
                                'max': float('-inf'),
                                'average': 0
                            },
                            'conditions': [],
                            'hourly': []
                        }
                    
                    # Add hourly data
                    temp = item.get('main', {}).get('temp')
                    humidity = item.get('main', {}).get('humidity')
                    
                    # Update min/max
                    daily_forecasts[date_key]['temperature']['min'] = min(daily_forecasts[date_key]['temperature']['min'], temp)
                    daily_forecasts[date_key]['temperature']['max'] = max(daily_forecasts[date_key]['temperature']['max'], temp)
                    daily_forecasts[date_key]['humidity']['min'] = min(daily_forecasts[date_key]['humidity']['min'], humidity)
                    daily_forecasts[date_key]['humidity']['max'] = max(daily_forecasts[date_key]['humidity']['max'], humidity)
                    
                    # Add condition if not already added
                    condition = item.get('weather', [{}])[0].get('main')
                    if condition and condition not in daily_forecasts[date_key]['conditions']:
                        daily_forecasts[date_key]['conditions'].append(condition)
                    
                    # Add hourly data
                    hourly_data = {
                        'time': dt.strftime('%H:%M'),
                        'temperature': temp,
                        'humidity': humidity,
                        'weather': {
                            'id': item.get('weather', [{}])[0].get('id'),
                            'main': item.get('weather', [{}])[0].get('main'),
                            'description': item.get('weather', [{}])[0].get('description'),
                            'icon': item.get('weather', [{}])[0].get('icon')
                        },
                        'wind': {
                            'speed': item.get('wind', {}).get('speed'),
                            'direction': item.get('wind', {}).get('deg')
                        }
                    }
                    daily_forecasts[date_key]['hourly'].append(hourly_data)
                
                # Calculate averages
                for date_key, day_data in daily_forecasts.items():
                    hourly_count = len(day_data['hourly'])
                    if hourly_count > 0:
                        temp_sum = sum(h['temperature'] for h in day_data['hourly'])
                        humidity_sum = sum(h['humidity'] for h in day_data['hourly'])
                        day_data['temperature']['average'] = temp_sum / hourly_count
                        day_data['humidity']['average'] = humidity_sum / hourly_count
                
                # Convert to list and sort by date
                forecast_list = list(daily_forecasts.values())
                forecast_list.sort(key=lambda x: x['date'])
                
                # Limit to requested days
                forecast_list = forecast_list[:days]
                
                # Combine with location info
                forecast = {
                    'coordinates': {
                        'latitude': latitude,
                        'longitude': longitude
                    },
                    'location': {
                        'name': data.get('city', {}).get('name'),
                        'country': data.get('city', {}).get('country')
                    },
                    'timezone': data.get('city', {}).get('timezone'),
                    'days': forecast_list
                }
                
                return forecast
            else:
                logger.error(f"OpenWeatherMap API error: {response.status_code} - {response.text}")
                raise ValueError(f"OpenWeatherMap forecast API error: {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.error(f"Error getting forecast data: {str(e)}")
            raise ValueError(f"Weather forecast retrieval failed: {str(e)}")
    
    def get_maintenance_recommendations(self, weather_data: Dict[str, Any], property_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Get maintenance recommendations based on weather and property data
        
        Args:
            weather_data: Current weather and forecast data
            property_data: Property information
            
        Returns:
            List of maintenance recommendations
        """
        logger.info("Generating maintenance recommendations")
        
        try:
            # Extract key weather data
            current_weather = weather_data.get('current', {})
            forecast = weather_data.get('forecast', {})
            
            current_temp = current_weather.get('temperature', {}).get('current')
            current_conditions = current_weather.get('weather', {}).get('main', '').lower()
            
            # Extract key property data
            property_type = property_data.get('property_type', 'residential')
            property_age = datetime.datetime.now().year - (property_data.get('year_built', 2000) or 2000)
            has_pool = property_data.get('has_pool', False)
            has_garden = property_data.get('has_garden', False)
            has_deck = property_data.get('has_deck', False)
            roof_type = property_data.get('roof_type', 'unknown')
            
            # Initialize recommendations list
            recommendations = []
            
            # Check for rain-related recommendations
            if 'rain' in current_conditions or any('Rain' in day.get('conditions', []) for day in forecast.get('days', [])):
                recommendations.append({
                    'type': 'rain',
                    'title': 'Check Gutters and Drainage',
                    'description': 'Ensure gutters are clear of debris and drainage is working properly to prevent water damage.',
                    'priority': 'high' if 'rain' in current_conditions else 'medium',
                    'seasonal': False,
                    'related_services': ['Gutter Cleaning', 'Drainage Inspection']
                })
                
                if property_age > 15 and roof_type != 'metal':
                    recommendations.append({
                        'type': 'rain',
                        'title': 'Inspect Roof for Leaks',
                        'description': 'Check attic and ceiling for signs of water intrusion, especially for older properties.',
                        'priority': 'medium',
                        'seasonal': False,
                        'related_services': ['Roof Inspection', 'Roof Repair']
                    })
            
            # Check for high wind recommendations
            wind_speed = current_weather.get('wind', {}).get('speed', 0)
            if wind_speed > 20:
                recommendations.append({
                    'type': 'wind',
                    'title': 'Secure Outdoor Items',
                    'description': f'Wind speeds of {wind_speed} mph detected. Secure or store outdoor furniture, decorations, and other loose items.',
                    'priority': 'high',
                    'seasonal': False,
                    'related_services': []
                })
                
                if property_age > 10:
                    recommendations.append({
                        'type': 'wind',
                        'title': 'Check for Loose Siding or Shingles',
                        'description': 'High winds can damage older siding and roofing. Inspect for loose or damaged materials.',
                        'priority': 'medium',
                        'seasonal': False,
                        'related_services': ['Siding Repair', 'Roof Inspection']
                    })
            
            # Check for snow/ice recommendations
            if 'snow' in current_conditions or any('Snow' in day.get('conditions', []) for day in forecast.get('days', [])):
                recommendations.append({
                    'type': 'snow',
                    'title': 'Clear Snow from Walkways',
                    'description': 'Keep walkways, driveways, and stairs clear of snow and ice to prevent accidents.',
                    'priority': 'high',
                    'seasonal': True,
                    'related_services': ['Snow Removal']
                })
                
                if property_age > 5:
                    recommendations.append({
                        'type': 'snow',
                        'title': 'Check for Ice Dams',
                        'description': 'Inspect roof edges for ice dams which can cause water damage to the roof and interior.',
                        'priority': 'medium',
                        'seasonal': True,
                        'related_services': ['Roof Inspection', 'Ice Dam Removal']
                    })
            
            # Temperature-based recommendations
            if current_temp is not None:
                # Hot weather recommendations
                if current_temp > 85:
                    recommendations.append({
                        'type': 'heat',
                        'title': 'HVAC Maintenance',
                        'description': f'High temperatures ({current_temp}°F) detected. Ensure AC system is functioning properly.',
                        'priority': 'medium',
                        'seasonal': True,
                        'related_services': ['HVAC Maintenance', 'AC Tune-up']
                    })
                    
                    if has_garden:
                        recommendations.append({
                            'type': 'heat',
                            'title': 'Garden Watering Schedule',
                            'description': 'Increase watering frequency during hot weather to protect plants.',
                            'priority': 'medium',
                            'seasonal': True,
                            'related_services': ['Landscaping', 'Garden Maintenance']
                        })
                    
                    if has_deck:
                        recommendations.append({
                            'type': 'heat',
                            'title': 'Check Deck for Heat Damage',
                            'description': 'Inspect wooden deck for signs of warping, cracking, or fading due to sun exposure.',
                            'priority': 'low',
                            'seasonal': True,
                            'related_services': ['Deck Maintenance', 'Deck Staining']
                        })
                
                # Cold weather recommendations
                if current_temp < 40:
                    recommendations.append({
                        'type': 'cold',
                        'title': 'Heating System Check',
                        'description': f'Low temperatures ({current_temp}°F) detected. Ensure heating system is functioning properly.',
                        'priority': 'high',
                        'seasonal': True,
                        'related_services': ['HVAC Maintenance', 'Heating System Tune-up']
                    })
                    
                    recommendations.append({
                        'type': 'cold',
                        'title': 'Protect Pipes from Freezing',
                        'description': 'Insulate exposed pipes and keep home heated to prevent frozen pipes.',
                        'priority': 'high' if current_temp < 32 else 'medium',
                        'seasonal': True,
                        'related_services': ['Plumbing Inspection', 'Pipe Insulation']
                    })
                    
                    if has_pool:
                        recommendations.append({
                            'type': 'cold',
                            'title': 'Pool Winterization',
                            'description': 'Ensure pool is properly winterized to prevent damage during freezing temperatures.',
                            'priority': 'medium',
                            'seasonal': True,
                            'related_services': ['Pool Maintenance', 'Pool Closing']
                        })
            
            # Seasonal recommendations based on month
            current_month = datetime.datetime.now().month
            
            # Spring recommendations (March-May)
            if 3 <= current_month <= 5:
                recommendations.append({
                    'type': 'seasonal',
                    'title': 'Spring Cleaning and Maintenance',
                    'description': 'Schedule comprehensive spring cleaning and maintenance for your property.',
                    'priority': 'medium',
                    'seasonal': True,
                    'related_services': ['Deep Cleaning', 'HVAC Maintenance', 'Gutter Cleaning']
                })
                
                if has_garden:
                    recommendations.append({
                        'type': 'seasonal',
                        'title': 'Garden Preparation',
                        'description': 'Prepare garden beds, prune shrubs, and plan your planting schedule.',
                        'priority': 'medium',
                        'seasonal': True,
                        'related_services': ['Landscaping', 'Garden Maintenance']
                    })
            
            # Summer recommendations (June-August)
            if 6 <= current_month <= 8:
                recommendations.append({
                    'type': 'seasonal',
                    'title': 'Summer Home Maintenance',
                    'description': 'Check AC system, inspect screen doors and windows, and maintain outdoor spaces.',
                    'priority': 'medium',
                    'seasonal': True,
                    'related_services': ['HVAC Maintenance', 'Window Repair', 'Deck Maintenance']
                })
                
                if has_pool:
                    recommendations.append({
                        'type': 'seasonal',
                        'title': 'Pool Maintenance',
                        'description': 'Regular pool cleaning and water treatment to keep it in optimal condition.',
                        'priority': 'high',
                        'seasonal': True,
                        'related_services': ['Pool Maintenance', 'Pool Cleaning']
                    })
            
            # Fall recommendations (September-November)
            if 9 <= current_month <= 11:
                recommendations.append({
                    'type': 'seasonal',
                    'title': 'Fall Preparation',
                    'description': 'Clear gutters, check heating system, and prepare for colder weather.',
                    'priority': 'high',
                    'seasonal': True,
                    'related_services': ['Gutter Cleaning', 'HVAC Maintenance', 'Roof Inspection']
                })
                
                if property_type.lower() == 'house':
                    recommendations.append({
                        'type': 'seasonal',
                        'title': 'Seal Air Leaks',
                        'description': 'Check for and seal air leaks around windows, doors, and other openings to improve energy efficiency.',
                        'priority': 'medium',
                        'seasonal': True,
                        'related_services': ['Weatherstripping', 'Window Caulking']
                    })
            
            # Winter recommendations (December-February)
            if current_month == 12 or current_month <= 2:
                recommendations.append({
                    'type': 'seasonal',
                    'title': 'Winter Home Protection',
                    'description': 'Protect your home from freezing temperatures, ice, and snow.',
                    'priority': 'high',
                    'seasonal': True,
                    'related_services': ['Heating System Maintenance', 'Pipe Insulation', 'Snow Removal']
                })
                
                if property_age > 20:
                    recommendations.append({
                        'type': 'seasonal',
                        'title': 'Inspect Attic Insulation',
                        'description': 'Check attic insulation for older homes to ensure heat retention and prevent ice dams.',
                        'priority': 'medium',
                        'seasonal': True,
                        'related_services': ['Insulation Installation', 'Energy Audit']
                    })
            
            # Add some property-specific recommendations
            if property_age > 30:
                recommendations.append({
                    'type': 'general',
                    'title': 'Older Home Inspection',
                    'description': f'Your home is {property_age} years old. Consider a comprehensive inspection to identify age-related issues.',
                    'priority': 'medium',
                    'seasonal': False,
                    'related_services': ['Home Inspection', 'Electrical Inspection', 'Plumbing Inspection']
                })
            
            # Sort recommendations by priority
            priority_order = {'high': 0, 'medium': 1, 'low': 2}
            recommendations.sort(key=lambda x: priority_order.get(x.get('priority'), 3))
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error generating maintenance recommendations: {str(e)}")
            raise ValueError(f"Failed to generate weather-based maintenance recommendations: {str(e)}")
    
    def get_energy_efficiency_tips(self, weather_data: Dict[str, Any], property_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Get energy efficiency tips based on weather and property data
        
        Args:
            weather_data: Current weather and forecast data
            property_data: Property information
            
        Returns:
            List of energy efficiency tips
        """
        logger.info("Generating energy efficiency tips")
        
        try:
            # Extract key weather data
            current_weather = weather_data.get('current', {})
            forecast = weather_data.get('forecast', {})
            
            current_temp = current_weather.get('temperature', {}).get('current')
            
            # Extract key property data
            property_type = property_data.get('property_type', 'residential')
            property_age = datetime.datetime.now().year - (property_data.get('year_built', 2000) or 2000)
            
            # Initialize tips list
            tips = []
            
            # Temperature-based tips
            if current_temp is not None:
                # Hot weather tips
                if current_temp > 80:
                    tips.append({
                        'type': 'cooling',
                        'title': 'Optimize Cooling Efficiency',
                        'description': 'During hot weather, close blinds during the day to block sunlight and use ceiling fans to improve air circulation.',
                        'estimated_savings': '$15-30 per month',
                        'difficulty': 'easy',
                        'seasonal': True
                    })
                    
                    tips.append({
                        'type': 'cooling',
                        'title': 'Programmable Thermostat',
                        'description': 'Set your thermostat to higher temperatures when away from home and normal temperatures when present.',
                        'estimated_savings': '$20-50 per month',
                        'difficulty': 'easy',
                        'seasonal': True
                    })
                
                # Cold weather tips
                if current_temp < 45:
                    tips.append({
                        'type': 'heating',
                        'title': 'Seal Drafts',
                        'description': 'Seal gaps around doors and windows to prevent cold air infiltration and heat loss.',
                        'estimated_savings': '$10-25 per month',
                        'difficulty': 'easy',
                        'seasonal': True
                    })
                    
                    tips.append({
                        'type': 'heating',
                        'title': 'Optimize Heating System',
                        'description': 'Lower thermostat by a few degrees and use space heaters in occupied rooms only when needed.',
                        'estimated_savings': '$15-40 per month',
                        'difficulty': 'easy',
                        'seasonal': True
                    })
            
            # General tips based on property age
            if property_age < 10:
                tips.append({
                    'type': 'general',
                    'title': 'Smart Home Integration',
                    'description': 'Consider integrating smart home technology for automated energy management.',
                    'estimated_savings': '$30-100 per month',
                    'difficulty': 'medium',
                    'seasonal': False
                })
            elif property_age < 30:
                tips.append({
                    'type': 'general',
                    'title': 'Upgrade to Energy-Efficient Appliances',
                    'description': 'Replace older appliances with ENERGY STAR certified models when they need replacement.',
                    'estimated_savings': '$20-80 per month',
                    'difficulty': 'medium',
                    'seasonal': False
                })
            else:
                tips.append({
                    'type': 'general',
                    'title': 'Energy Audit',
                    'description': 'Schedule a professional energy audit to identify areas for improvement in older homes.',
                    'estimated_savings': '$50-200 per month',
                    'difficulty': 'medium',
                    'seasonal': False
                })
                
                tips.append({
                    'type': 'insulation',
                    'title': 'Upgrade Insulation',
                    'description': 'Older homes often have insufficient insulation. Adding modern insulation can significantly reduce energy costs.',
                    'estimated_savings': '$30-100 per month',
                    'difficulty': 'hard',
                    'seasonal': False
                })
            
            # Additional general tips
            tips.append({
                'type': 'lighting',
                'title': 'LED Lighting Upgrade',
                'description': 'Replace conventional bulbs with LED lights for significant energy savings.',
                'estimated_savings': '$5-15 per month',
                'difficulty': 'easy',
                'seasonal': False
            })
            
            tips.append({
                'type': 'water',
                'title': 'Water Conservation',
                'description': 'Install low-flow fixtures and check for leaks to reduce water usage and energy for water heating.',
                'estimated_savings': '$10-30 per month',
                'difficulty': 'easy',
                'seasonal': False
            })
            
            if property_type.lower() == 'house':
                tips.append({
                    'type': 'landscaping',
                    'title': 'Strategic Landscaping',
                    'description': 'Plant shade trees on the south and west sides of your home to reduce cooling costs in summer.',
                    'estimated_savings': '$10-50 per year',
                    'difficulty': 'medium',
                    'seasonal': False
                })
            
            # Randomize the order a bit while keeping the most relevant ones first
            import random
            seasonal_tips = [tip for tip in tips if tip.get('seasonal', False)]
            general_tips = [tip for tip in tips if not tip.get('seasonal', False)]
            
            # Keep seasonal tips at the top if applicable to current weather
            if seasonal_tips:
                random.shuffle(seasonal_tips)
                seasonal_tips = seasonal_tips[:2]  # Limit to top 2 seasonal tips
            
            random.shuffle(general_tips)
            general_tips = general_tips[:3]  # Limit to top 3 general tips
            
            return seasonal_tips + general_tips
            
        except Exception as e:
            logger.error(f"Error generating energy efficiency tips: {str(e)}")
            raise ValueError(f"Failed to generate energy efficiency tips: {str(e)}")
    
    def _generate_fallback_weather_data(self, latitude: float, longitude: float) -> Dict[str, Any]:
        """Generate fallback weather data when API is not available"""
        # Get current date and time
        now = datetime.datetime.now()
        
        # Generate reasonable weather based on latitude and month
        month = now.month
        
        # Rough temperature estimate based on latitude and month
        # Higher latitudes = colder, especially in winter
        base_temp = 75  # Base temperature (°F)
        
        # Adjust for hemisphere (northern or southern)
        is_northern = latitude > 0
        
        # Adjust month based on hemisphere (flip seasons)
        if not is_northern:
            month = (month + 6) % 12
            if month == 0:
                month = 12
        
        # Temperature adjustments
        # Northern hemisphere: coldest in Jan (1), warmest in July (7)
        # Southern hemisphere: coldest in July (7), warmest in Jan (1)
        month_temp_adjustment = {
            1: -15 if is_northern else 15,
            2: -10 if is_northern else 10,
            3: -5 if is_northern else 5,
            4: 0 if is_northern else 0,
            5: 5 if is_northern else -5,
            6: 10 if is_northern else -10,
            7: 15 if is_northern else -15,
            8: 10 if is_northern else -10,
            9: 5 if is_northern else -5,
            10: 0 if is_northern else 0,
            11: -5 if is_northern else 5,
            12: -10 if is_northern else 10
        }
        
        # Latitude adjustment (roughly -2°F per 5° latitude away from equator)
        lat_adjustment = abs(latitude) * -0.4
        
        # Calculate adjusted temperature
        adjusted_temp = base_temp + month_temp_adjustment.get(month, 0) + lat_adjustment
        
        # Add some randomness (+/- 5°F)
        import random
        adjusted_temp += random.uniform(-5, 5)
        
        # Determine weather condition based on temp and randomness
        conditions = ['Clear', 'Clouds', 'Rain', 'Snow']
        weights = [0.4, 0.3, 0.2, 0.1]  # Default weights
        
        # Adjust weights based on temperature
        if adjusted_temp < 32:  # Cold enough for snow
            weights = [0.2, 0.3, 0.1, 0.4]
        elif adjusted_temp < 45:  # Cold but not freezing
            weights = [0.2, 0.4, 0.3, 0.1]
        elif adjusted_temp > 80:  # Hot
            weights = [0.6, 0.3, 0.1, 0]
        
        # Select condition
        condition = random.choices(conditions, weights=weights)[0]
        
        # Generate reasonable humidity
        if condition == 'Rain' or condition == 'Snow':
            humidity = random.uniform(70, 95)
        elif condition == 'Clear' and adjusted_temp > 75:
            humidity = random.uniform(40, 70)
        else:
            humidity = random.uniform(30, 80)
        
        # Generate wind speed
        wind_speed = random.uniform(3, 15)
        
        # Map condition to OpenWeatherMap format
        condition_map = {
            'Clear': {'id': 800, 'main': 'Clear', 'description': 'clear sky', 'icon': '01d'},
            'Clouds': {'id': 803, 'main': 'Clouds', 'description': 'broken clouds', 'icon': '03d'},
            'Rain': {'id': 500, 'main': 'Rain', 'description': 'light rain', 'icon': '10d'},
            'Snow': {'id': 600, 'main': 'Snow', 'description': 'light snow', 'icon': '13d'}
        }
        
        return {
            'coordinates': {
                'latitude': latitude,
                'longitude': longitude
            },
            'temperature': {
                'current': round(adjusted_temp, 1),
                'feels_like': round(adjusted_temp - 2 if wind_speed > 10 else adjusted_temp, 1),
                'min': round(adjusted_temp - random.uniform(3, 8), 1),
                'max': round(adjusted_temp + random.uniform(3, 8), 1)
            },
            'humidity': round(humidity),
            'pressure': 1013,  # Standard atmospheric pressure
            'wind': {
                'speed': round(wind_speed, 1),
                'direction': random.randint(0, 359)
            },
            'clouds': 0 if condition == 'Clear' else random.randint(20, 90),
            'weather': condition_map.get(condition, condition_map['Clear']),
            'timestamp': int(now.timestamp()),
            'location': {
                'name': 'Unknown Location',
                'country': 'US'
            },
            'sunrise': int((now.replace(hour=6, minute=0, second=0)).timestamp()),
            'sunset': int((now.replace(hour=20, minute=0, second=0)).timestamp()),
            'timezone': 0
        }
    
    def _generate_fallback_forecast_data(self, latitude: float, longitude: float, days: int) -> Dict[str, Any]:
        """Generate fallback forecast data when API is not available"""
        forecast_days = []
        now = datetime.datetime.now()
        
        # Generate a forecast for each day
        for day_offset in range(days):
            forecast_date = now + datetime.timedelta(days=day_offset)
            date_key = forecast_date.strftime('%Y-%m-%d')
            
            # Generate fake but reasonable daily weather
            # More variation as we go further into the future
            variation_factor = day_offset * 0.5 + 1
            
            # Get base weather for the day
            base_weather = self._generate_fallback_weather_data(latitude, longitude)
            
            # Adjust temperature with more variation for future days
            import random
            temp_adjustment = random.uniform(-5, 5) * variation_factor
            base_temp = base_weather['temperature']['current'] + temp_adjustment
            
            # Generate hourly data (simplified to 4 points per day)
            hourly_data = []
            for hour in [8, 12, 16, 20]:  # Morning, noon, afternoon, evening
                # Temperature varies throughout the day
                hour_temp_adjustment = 0
                if hour == 8:  # Morning
                    hour_temp_adjustment = -5
                elif hour == 12:  # Noon
                    hour_temp_adjustment = 5
                elif hour == 16:  # Afternoon
                    hour_temp_adjustment = 3
                elif hour == 20:  # Evening
                    hour_temp_adjustment = -3
                
                hourly_data.append({
                    'time': f'{hour:02d}:00',
                    'temperature': round(base_temp + hour_temp_adjustment, 1),
                    'humidity': base_weather['humidity'] + random.randint(-10, 10),
                    'weather': base_weather['weather'],  # Use same weather condition
                    'wind': {
                        'speed': base_weather['wind']['speed'] + random.uniform(-2, 2),
                        'direction': base_weather['wind']['direction'] + random.randint(-30, 30) % 360
                    }
                })
            
            # Calculate min/max/avg from hourly data
            temps = [h['temperature'] for h in hourly_data]
            humidity = [h['humidity'] for h in hourly_data]
            
            forecast_days.append({
                'date': date_key,
                'day_of_week': forecast_date.strftime('%A'),
                'temperature': {
                    'min': min(temps),
                    'max': max(temps),
                    'average': sum(temps) / len(temps)
                },
                'humidity': {
                    'min': min(humidity),
                    'max': max(humidity),
                    'average': sum(humidity) / len(humidity)
                },
                'conditions': [base_weather['weather']['main']],
                'hourly': hourly_data
            })
        
        return {
            'coordinates': {
                'latitude': latitude,
                'longitude': longitude
            },
            'location': {
                'name': 'Unknown Location',
                'country': 'US'
            },
            'timezone': 0,
            'days': forecast_days
        }
    
    def _generate_fallback_recommendations(self, property_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate fallback maintenance recommendations when API is not available"""
        # Get current month for seasonal recommendations
        current_month = datetime.datetime.now().month
        
        # Generate property age if not provided
        property_age = datetime.datetime.now().year - (property_data.get('year_built', 2000) or 2000)
        
        # Initialize recommendations
        recommendations = []
        
        # Add general recommendations
        recommendations.append({
            'type': 'general',
            'title': 'Regular Home Inspection',
            'description': 'Perform regular inspections of your property to identify potential issues early.',
            'priority': 'medium',
            'seasonal': False,
            'related_services': ['Home Inspection']
        })
        
        # Add recommendation based on property age
        if property_age > 20:
            recommendations.append({
                'type': 'general',
                'title': 'Check Electrical System',
                'description': f'Your home is {property_age} years old. Consider having your electrical system inspected for safety and efficiency.',
                'priority': 'medium',
                'seasonal': False,
                'related_services': ['Electrical Inspection', 'Electrical Repair']
            })
        
        # Add seasonal recommendations
        # Spring (March-May)
        if 3 <= current_month <= 5:
            recommendations.append({
                'type': 'seasonal',
                'title': 'Spring Maintenance',
                'description': 'Check for winter damage, clean gutters, and prepare cooling systems.',
                'priority': 'medium',
                'seasonal': True,
                'related_services': ['Gutter Cleaning', 'HVAC Maintenance']
            })
        # Summer (June-August)
        elif 6 <= current_month <= 8:
            recommendations.append({
                'type': 'seasonal',
                'title': 'Summer Maintenance',
                'description': 'Check cooling system efficiency, inspect for pest intrusion, and maintain outdoor spaces.',
                'priority': 'medium',
                'seasonal': True,
                'related_services': ['HVAC Maintenance', 'Pest Control', 'Lawn Care']
            })
        # Fall (September-November)
        elif 9 <= current_month <= 11:
            recommendations.append({
                'type': 'seasonal',
                'title': 'Fall Maintenance',
                'description': 'Prepare for colder weather, clean gutters, and check heating systems.',
                'priority': 'high',
                'seasonal': True,
                'related_services': ['Gutter Cleaning', 'HVAC Maintenance', 'Roof Inspection']
            })
        # Winter (December-February)
        else:
            recommendations.append({
                'type': 'seasonal',
                'title': 'Winter Maintenance',
                'description': 'Monitor for ice dams, check heating system efficiency, and protect pipes from freezing.',
                'priority': 'high',
                'seasonal': True,
                'related_services': ['Heating System Maintenance', 'Pipe Insulation']
            })
        
        return recommendations
    
    def _generate_fallback_energy_tips(self) -> List[Dict[str, Any]]:
        """Generate fallback energy efficiency tips when API is not available"""
        # General energy efficiency tips that are always applicable
        return [
            {
                'type': 'general',
                'title': 'Programmable Thermostat',
                'description': 'Install a programmable thermostat to automatically adjust temperature settings throughout the day.',
                'estimated_savings': '$15-35 per month',
                'difficulty': 'easy',
                'seasonal': False
            },
            {
                'type': 'general',
                'title': 'LED Lighting',
                'description': 'Replace conventional bulbs with LED lighting for significant energy savings.',
                'estimated_savings': '$5-15 per month',
                'difficulty': 'easy',
                'seasonal': False
            },
            {
                'type': 'general',
                'title': 'Seal Air Leaks',
                'description': 'Seal gaps around doors, windows, and other openings to prevent air leakage.',
                'estimated_savings': '$10-25 per month',
                'difficulty': 'easy',
                'seasonal': False
            },
            {
                'type': 'general',
                'title': 'Energy Star Appliances',
                'description': 'When replacing appliances, choose ENERGY STAR certified models for better efficiency.',
                'estimated_savings': '$8-40 per month',
                'difficulty': 'medium',
                'seasonal': False
            },
            {
                'type': 'general',
                'title': 'Insulation Upgrade',
                'description': 'Improve your home\'s insulation, especially in the attic, to reduce heating and cooling costs.',
                'estimated_savings': '$20-45 per month',
                'difficulty': 'hard',
                'seasonal': False
            }
        ]


# API routes
@weather_bp.route('/current', methods=['POST'])
def current_weather():
    """Get current weather data for coordinates"""
    try:
        data = request.json
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'No data provided'
            }), 400
        
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        
        if latitude is None or longitude is None:
            return jsonify({
                'success': False,
                'message': 'Latitude and longitude are required'
            }), 400
        
        # Get current weather
        weather = WeatherIntegration()
        weather_data = weather.get_current_weather(latitude, longitude)
        
        return jsonify({
            'success': True,
            'weather': weather_data
        })
        
    except Exception as e:
        logger.error(f"Error in current weather API: {str(e)}")
        return jsonify({
            'success': False,
            'message': f"Failed to get current weather: {str(e)}"
        }), 500


@weather_bp.route('/forecast', methods=['POST'])
def weather_forecast():
    """Get weather forecast for coordinates"""
    try:
        data = request.json
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'No data provided'
            }), 400
        
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        days = data.get('days', 5)
        
        if latitude is None or longitude is None:
            return jsonify({
                'success': False,
                'message': 'Latitude and longitude are required'
            }), 400
        
        # Ensure days is a valid number
        try:
            days = int(days)
            if days < 1:
                days = 1
            elif days > 5:
                days = 5
        except (ValueError, TypeError):
            days = 5
        
        # Get forecast
        weather = WeatherIntegration()
        forecast_data = weather.get_forecast(latitude, longitude, days)
        
        return jsonify({
            'success': True,
            'forecast': forecast_data
        })
        
    except Exception as e:
        logger.error(f"Error in forecast API: {str(e)}")
        return jsonify({
            'success': False,
            'message': f"Failed to get forecast: {str(e)}"
        }), 500


@weather_bp.route('/maintenance-recommendations', methods=['POST'])
def maintenance_recommendations():
    """Get maintenance recommendations based on weather and property data"""
    try:
        data = request.json
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'No data provided'
            }), 400
        
        weather_data = data.get('weather_data', {})
        property_data = data.get('property_data', {})
        
        if not weather_data or not property_data:
            return jsonify({
                'success': False,
                'message': 'Weather data and property data are required'
            }), 400
        
        # Get recommendations
        weather = WeatherIntegration()
        recommendations = weather.get_maintenance_recommendations(weather_data, property_data)
        
        return jsonify({
            'success': True,
            'recommendations': recommendations
        })
        
    except Exception as e:
        logger.error(f"Error in maintenance recommendations API: {str(e)}")
        return jsonify({
            'success': False,
            'message': f"Failed to get maintenance recommendations: {str(e)}"
        }), 500


@weather_bp.route('/energy-tips', methods=['POST'])
def energy_tips():
    """Get energy efficiency tips based on weather and property data"""
    try:
        data = request.json
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'No data provided'
            }), 400
        
        weather_data = data.get('weather_data', {})
        property_data = data.get('property_data', {})
        
        if not weather_data or not property_data:
            return jsonify({
                'success': False,
                'message': 'Weather data and property data are required'
            }), 400
        
        # Get energy tips
        weather = WeatherIntegration()
        tips = weather.get_energy_efficiency_tips(weather_data, property_data)
        
        return jsonify({
            'success': True,
            'tips': tips
        })
        
    except Exception as e:
        logger.error(f"Error in energy tips API: {str(e)}")
        return jsonify({
            'success': False,
            'message': f"Failed to get energy efficiency tips: {str(e)}"
        }), 500