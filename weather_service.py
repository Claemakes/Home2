"""
Weather Service for GlassRain

A simple wrapper around the OpenWeather API for GlassRain to provide
weather information for properties.
"""

import os
import json
import logging
import requests
from flask import Blueprint, request, jsonify

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WeatherService:
    """Weather service using OpenWeather API"""
    def __init__(self, api_key=None):
        """Initialize the weather service"""
        self.api_key = api_key or os.environ.get('OPENWEATHER_API_KEY', os.environ.get('WEATHERAPI_KEY', ''))
        
        if not self.api_key:
            logger.warning("No API key provided for Weather Service")
            
    def get_weather(self, latitude, longitude):
        """Get current weather for a location"""
        if not self.api_key:
            logger.error("Cannot fetch weather data without API key")
            return {}
            
        try:
            # Build the API URL
            url = f"https://api.openweathermap.org/data/2.5/weather"
            params = {
                "lat": latitude,
                "lon": longitude,
                "appid": self.api_key,
                "units": "imperial"  # Use imperial units for US locations
            }
            
            # Make the request
            response = requests.get(url, params=params, timeout=10)
            
            # Check for successful response
            if response.status_code != 200:
                logger.error(f"Error fetching weather data: {response.status_code} - {response.text}")
                return {}
                
            # Parse the JSON response
            data = response.json()
            
            # Format the weather data for our application
            weather = {
                "temperature": data.get("main", {}).get("temp"),
                "feels_like": data.get("main", {}).get("feels_like"),
                "humidity": data.get("main", {}).get("humidity"),
                "description": data.get("weather", [{}])[0].get("description", "").capitalize(),
                "icon": data.get("weather", [{}])[0].get("icon"),
                "wind_speed": data.get("wind", {}).get("speed"),
                "location": data.get("name")
            }
            
            return weather
        except Exception as e:
            logger.error(f"Error fetching weather data: {str(e)}")
            return {}
            
    def get_forecast(self, latitude, longitude, days=5):
        """Get weather forecast for a location"""
        if not self.api_key:
            logger.error("Cannot fetch forecast data without API key")
            return []
            
        try:
            # Build the API URL
            url = f"https://api.openweathermap.org/data/2.5/forecast"
            params = {
                "lat": latitude,
                "lon": longitude,
                "appid": self.api_key,
                "units": "imperial",  # Use imperial units for US locations
                "cnt": days * 8  # 8 time periods per day (every 3 hours)
            }
            
            # Make the request
            response = requests.get(url, params=params, timeout=10)
            
            # Check for successful response
            if response.status_code != 200:
                logger.error(f"Error fetching forecast data: {response.status_code} - {response.text}")
                return []
                
            # Parse the JSON response
            data = response.json()
            
            # Format the forecast data for our application
            forecast = []
            
            for item in data.get("list", []):
                forecast_item = {
                    "datetime": item.get("dt_txt"),
                    "temperature": item.get("main", {}).get("temp"),
                    "feels_like": item.get("main", {}).get("feels_like"),
                    "humidity": item.get("main", {}).get("humidity"),
                    "description": item.get("weather", [{}])[0].get("description", "").capitalize(),
                    "icon": item.get("weather", [{}])[0].get("icon"),
                    "wind_speed": item.get("wind", {}).get("speed")
                }
                forecast.append(forecast_item)
            
            return forecast
        except Exception as e:
            logger.error(f"Error fetching forecast data: {str(e)}")
            return []

# Define a Blueprint for weather-related routes
weather_bp = Blueprint('weather', __name__)

@weather_bp.route('/current')
def get_current_weather():
    """Get current weather for a location"""
    try:
        # Get location from query parameters
        latitude = request.args.get('latitude', type=float)
        longitude = request.args.get('longitude', type=float)
        
        if not latitude or not longitude:
            return jsonify({"error": "Latitude and longitude are required"}), 400
            
        # Get API key
        api_key = os.environ.get('OPENWEATHER_API_KEY', os.environ.get('WEATHERAPI_KEY', ''))
        
        if not api_key:
            return jsonify({"error": "Weather API key not configured"}), 500
            
        # Create a weather service instance
        weather_service = WeatherService(api_key)
        
        # Get weather data
        weather = weather_service.get_weather(latitude, longitude)
        
        if not weather:
            return jsonify({"error": "Failed to fetch weather data"}), 500
            
        return jsonify(weather)
    except Exception as e:
        logger.error(f"Error in weather endpoint: {str(e)}")
        return jsonify({"error": str(e)}), 500

@weather_bp.route('/forecast')
def get_weather_forecast():
    """Get weather forecast for a location"""
    try:
        # Get location from query parameters
        latitude = request.args.get('latitude', type=float)
        longitude = request.args.get('longitude', type=float)
        days = request.args.get('days', 5, type=int)
        
        if not latitude or not longitude:
            return jsonify({"error": "Latitude and longitude are required"}), 400
            
        # Get API key
        api_key = os.environ.get('OPENWEATHER_API_KEY', os.environ.get('WEATHERAPI_KEY', ''))
        
        if not api_key:
            return jsonify({"error": "Weather API key not configured"}), 500
            
        # Create a weather service instance
        weather_service = WeatherService(api_key)
        
        # Get forecast data
        forecast = weather_service.get_forecast(latitude, longitude, days)
        
        if not forecast:
            return jsonify({"error": "Failed to fetch forecast data"}), 500
            
        return jsonify(forecast)
    except Exception as e:
        logger.error(f"Error in forecast endpoint: {str(e)}")
        return jsonify({"error": str(e)}), 500