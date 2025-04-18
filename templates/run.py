#!/usr/bin/env python3
"""
GlassRain - Intelligent Property Platform
Main Application Entry Point
"""
import os
import json
import logging
import uuid
import base64
from datetime import datetime
import requests
from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix
import psycopg2
from psycopg2.extras import RealDictCursor
import psycopg2.extras
import store_products

# Import configuration
try:
    from config import MAPBOX_API_KEY, AWS_ACCESS_KEY, AWS_SECRET_KEY, AWS_REGION
    from config import DYNAMODB_TABLE_HOMES, DYNAMODB_TABLE_USERS, DYNAMODB_TABLE_SCANS
    from config import DYNAMODB_TABLE_SERVICES, DYNAMODB_TABLE_QUOTES
except ImportError:
    # Fallback to environment variables if config module is not available
    MAPBOX_API_KEY = os.environ.get('MAPBOX_API_KEY', '')
    AWS_ACCESS_KEY = os.environ.get('AWS_ACCESS_KEY', '')
    AWS_SECRET_KEY = os.environ.get('AWS_SECRET_KEY', '')
    AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')
    DYNAMODB_TABLE_HOMES = os.environ.get('DYNAMODB_TABLE_HOMES', 'glassrain-homes')
    DYNAMODB_TABLE_USERS = os.environ.get('DYNAMODB_TABLE_USERS', 'glassrain-users')
    DYNAMODB_TABLE_SCANS = os.environ.get('DYNAMODB_TABLE_SCANS', 'glassrain-scans')
    DYNAMODB_TABLE_SERVICES = os.environ.get('DYNAMODB_TABLE_SERVICES', 'glassrain-services')
    DYNAMODB_TABLE_QUOTES = os.environ.get('DYNAMODB_TABLE_QUOTES', 'glassrain-quotes')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('glassrain.log')
    ]
)
logger = logging.getLogger('glassrain')

# Initialize OpenAI API
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
if OPENAI_API_KEY:
    try:
        import openai
        from openai import OpenAI
        import httpx
        # Create httpx client explicitly without proxies
        http_client = httpx.Client(timeout=60.0)
        client = OpenAI(api_key=OPENAI_API_KEY, http_client=http_client)
        logger.info("✅ OpenAI API initialized successfully")
    except Exception as e:
        logger.error(f"❌ Error initializing OpenAI: {str(e)}")
        client = None
else:
    logger.warning("⚠️ OpenAI API key not found in environment variables")
    client = None

# Import GlassRain components
try:
    from enhanced_ai_design_assistant import DesignAssistant
    logger.info("✅ Enhanced AI Design Assistant imported")
except ImportError:
    logger.warning("⚠️ Enhanced AI Design Assistant not available")
    class DesignAssistant:
        def __init__(self): pass
        
try:
    from enhanced_mapbox_integration import MapboxIntegration
    logger.info("✅ Mapbox Integration imported")
except ImportError:
    logger.warning("⚠️ Mapbox Integration not available")
    class MapboxIntegration:
        def __init__(self, api_key=None): pass
        
try:
    from diy_assistant import DIYAssistant
    logger.info("✅ DIY Assistant imported")
except ImportError:
    logger.warning("⚠️ DIY Assistant not available")
    class DIYAssistant:
        def __init__(self, api_key=None): pass
        
try:
    from enhanced_weather_integration import weather_bp
    from weather_service import WeatherService
    logger.info("✅ Weather Service imported")
except ImportError:
    logger.warning("⚠️ Weather Service not available")
    class WeatherService:
        def __init__(self, api_key=None): pass
        def get_weather(self, lat, lng): return {}
    # Create an empty Blueprint for weather
    from flask import Blueprint
    weather_bp = Blueprint('weather', __name__)
        
try:
    from user_authentication import UserAuth
    logger.info("✅ User Authentication imported")
except ImportError:
    logger.warning("⚠️ User Authentication not available")
    class UserAuth:
        def __init__(self): pass
        def login(self, email, password): return True
        def register(self, email, password, first_name, last_name): return True
        
try:
    from enhanced_property_data_service import EnhancedPropertyDataService
    logger.info("✅ Enhanced Property Data Service imported")
except ImportError:
    logger.warning("⚠️ Enhanced Property Data Service not available")
    class EnhancedPropertyDataService:
        def __init__(self): pass
        def calculate_energy_score(self, year_built, square_footage): return 78
        def generate_3d_home_model(self, lat, lng, address): return {}

# Initialize Flask app
app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

# Register blueprints
app.register_blueprint(weather_bp, url_prefix='/api/weather')

# Register AI Design blueprint
try:
    from ai_design_routes import ai_design_bp
    app.register_blueprint(ai_design_bp)
    logger.info("✅ AI Design Blueprint registered successfully")
except ImportError:
    logger.warning("⚠️ AI Design Blueprint not available")

# Configure secure session management
try:
    from session_management import configure_session, login_required
    app = configure_session(app)
    logger.info("✅ Session management configured")
except ImportError:
    logger.warning("⚠️ Session management not available")
    # Fallback for session configuration
    app.secret_key = os.environ.get('SECRET_KEY', 'development-key')
    # Simple login_required decorator
    def login_required(f):
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('login'))
            return f(*args, **kwargs)
        return decorated_function

# Initialize components
design_assistant = DesignAssistant()
mapbox = MapboxIntegration(api_key=os.environ.get('MAPBOX_API_KEY', ''))
diy_assistant = DIYAssistant(api_key=os.environ.get('OPENAI_API_KEY', ''))
weather_service = WeatherService(api_key=os.environ.get('OPENWEATHER_API_KEY', ''))
user_auth = UserAuth()
property_data = EnhancedPropertyDataService()

# Database connection
def get_db_connection():
    """Get a database connection"""
    try:
        conn = psycopg2.connect(
            os.environ.get('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/postgres')
        )
        conn.autocommit = True
        return conn
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        return None

# Database initialization
def setup_database():
    """Setup the database tables if they don't exist"""
    try:
        logger.info("Setting up database tables...")
        conn = get_db_connection()
        if not conn:
            logger.error("Failed to connect to database for setup")
            return False
            
        cursor = conn.cursor()
        
        # Create addresses table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS addresses (
                address_id SERIAL PRIMARY KEY,
                street TEXT NOT NULL,
                city TEXT NOT NULL,
                state TEXT NOT NULL,
                zip TEXT NOT NULL,
                country TEXT NOT NULL,
                latitude FLOAT NOT NULL,
                longitude FLOAT NOT NULL,
                property_type TEXT,
                year_built INTEGER,
                square_footage INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id SERIAL PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                first_name TEXT,
                last_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create user_addresses (relationship table)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_addresses (
                user_id INTEGER REFERENCES users(user_id),
                address_id INTEGER REFERENCES addresses(address_id),
                is_primary BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, address_id)
            )
        ''')
        
        # Create service_categories table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS service_categories (
                category_id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                icon_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create services table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS services (
                service_id SERIAL PRIMARY KEY,
                category_id INTEGER REFERENCES service_categories(category_id),
                name TEXT NOT NULL,
                description TEXT,
                base_price NUMERIC,
                base_price_per_sqft NUMERIC,
                min_price NUMERIC,
                duration_minutes INTEGER,
                price_unit VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create service_tiers table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS service_tiers (
                tier_id SERIAL PRIMARY KEY,
                service_id INTEGER REFERENCES services(service_id),
                name TEXT NOT NULL,
                description TEXT,
                multiplier NUMERIC,
                features JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create contractors table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS contractors (
                contractor_id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                email VARCHAR(255),
                phone VARCHAR(50),
                address TEXT,
                city VARCHAR(100),
                state VARCHAR(50),
                zip_code VARCHAR(20),
                years_in_business INTEGER,
                years_experience INTEGER,
                license_verified BOOLEAN DEFAULT FALSE,
                insurance_verified BOOLEAN DEFAULT FALSE,
                description TEXT,
                logo_url TEXT,
                website_url TEXT,
                business_size VARCHAR(50),
                tier_level TEXT,
                rating NUMERIC(3,1),
                review_count INTEGER DEFAULT 0,
                service_areas TEXT[],
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create contractor_services (relationship table)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS contractor_services (
                contractor_id INTEGER REFERENCES contractors(contractor_id),
                service_id INTEGER REFERENCES services(service_id),
                tier_id INTEGER REFERENCES service_tiers(tier_id),
                PRIMARY KEY (contractor_id, service_id, tier_id)
            )
        ''')
        
        # Create service_requests table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS service_requests (
                request_id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(user_id),
                address_id INTEGER REFERENCES addresses(address_id),
                service_id INTEGER REFERENCES services(service_id),
                tier_id INTEGER REFERENCES service_tiers(tier_id),
                contractor_id INTEGER REFERENCES contractors(contractor_id) NULL,
                status TEXT DEFAULT 'pending',
                details TEXT,
                requested_date DATE,
                price NUMERIC,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create DIY projects table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS diy_projects (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT,
                difficulty TEXT,
                estimated_time TEXT,
                materials TEXT[],
                steps TEXT[],
                image_url TEXT
            )
        ''')
        
        # Create user_projects (saved DIY projects)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_projects (
                user_id INTEGER REFERENCES users(user_id),
                project_id INTEGER REFERENCES diy_projects(id),
                status TEXT DEFAULT 'saved',
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, project_id)
            )
        ''')
        
        # Create property_models table for 3D models and data
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS property_models (
                address_id INTEGER REFERENCES addresses(address_id),
                model_data JSONB,
                energy_score INTEGER,
                maintenance_data JSONB,
                weather_data JSONB,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (address_id)
            )
        ''')
        
        # Create scanned_rooms table for the Elevate tab
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scanned_rooms (
                id SERIAL PRIMARY KEY,
                user_id INTEGER,
                name TEXT NOT NULL,
                room_type TEXT NOT NULL,
                width FLOAT,
                length FLOAT,
                height FLOAT,
                area FLOAT,
                walls_area FLOAT,
                volume FLOAT,
                windows INTEGER,
                doors INTEGER,
                scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                thumbnail_url TEXT,
                model_url TEXT
            )
        ''')
        
        # Create room_measurements table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS room_measurements (
                id SERIAL PRIMARY KEY,
                room_id INTEGER REFERENCES scanned_rooms(id) ON DELETE CASCADE,
                measurement_type TEXT NOT NULL,
                value FLOAT NOT NULL,
                unit TEXT NOT NULL
            )
        ''')
        
        # Create room_designs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS room_designs (
                id SERIAL PRIMARY KEY,
                user_id INTEGER,
                room_id INTEGER REFERENCES scanned_rooms(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                thumbnail_url TEXT,
                chat_history JSONB DEFAULT '[]',
                measurements JSONB DEFAULT '{}',
                tags JSONB DEFAULT '[]'
            )
        ''')
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info("Database setup completed successfully")
        return True
    except Exception as e:
        logger.error(f"Error setting up database: {e}")
        return False

# Run database setup
setup_database()

# Main routes
@app.route('/')
def index():
<<<<<<< HEAD
    """Render the index page"""
    return render_template('index.html')
=======
    return render_template('address_entry.html')
>>>>>>> 78aef21 (Add address entry page to property visualization platform.)

@app.route('/dashboard')
def dashboard():
    """Render the dashboard page"""
    address_id = request.args.get('address_id')
    
    if not address_id:
        # If no address is selected, show the dashboard anyway
        # User can add an address from dashboard
        return render_template('dashboard.html')
    
    try:
        conn = get_db_connection()
        if not conn:
            return render_template('dashboard.html', error="Database connection failed")
            
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get address details
        cursor.execute("""
            SELECT * FROM addresses WHERE address_id = %s
        """, (address_id,))
        
        address = cursor.fetchone()
        
        if not address:
            return render_template('dashboard.html', error="Address not found")
            
        # Get property model
        cursor.execute("""
            SELECT * FROM property_models WHERE address_id = %s
        """, (address_id,))
        
        property_model = cursor.fetchone()
        
        # Calculate energy score if model exists or property_data service is available
        energy_score = 0
        if property_model and property_model.get('energy_score'):
            energy_score = property_model['energy_score']
        elif hasattr(property_data, 'calculate_energy_score'):
            energy_score = property_data.calculate_energy_score(
                address.get('year_built', 2000),
                address.get('square_footage', 2000)
            )
        
        # Get weather data
        weather_data = None
        if hasattr(weather_service, 'get_weather'):
            weather_data = weather_service.get_weather(
                address.get('latitude'),
                address.get('longitude')
            )
        
        # Generate 3D model if it doesn't exist
        model_data = {}
        if property_model and property_model.get('model_data'):
            model_data = property_model['model_data']
        elif hasattr(property_data, 'generate_3d_home_model'):
            model_data = property_data.generate_3d_home_model(
                address.get('latitude'),
                address.get('longitude'),
                f"{address.get('street')}, {address.get('city')}, {address.get('state')} {address.get('zip')}"
            )
            
            # Save the generated model to the database
            if model_data:
                try:
                    cursor.execute("""
                        INSERT INTO property_models (address_id, model_data, energy_score, updated_at)
                        VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                        ON CONFLICT (address_id) 
                        DO UPDATE SET model_data = %s, energy_score = %s, updated_at = CURRENT_TIMESTAMP
                    """, (
                        address_id,
                        json.dumps(model_data),
                        energy_score,
                        json.dumps(model_data),
                        energy_score
                    ))
                except Exception as e:
                    logger.error(f"Error saving property model: {e}")
        
        # Get service recommendations
        service_recommendations = []
        try:
            from service_recommendations import get_recommendations_for_property
            service_recommendations = get_recommendations_for_property(address_id)
        except ImportError:
            logger.warning("Service recommendations module not available")
        except Exception as e:
            logger.error(f"Error getting service recommendations: {e}")
        
        cursor.close()
        conn.close()
        
        return render_template(
            'dashboard.html',
            address=address,
            model_data=model_data,
            energy_score=energy_score,
            weather_data=weather_data,
            service_recommendations=service_recommendations
        )
        
    except Exception as e:
        logger.error(f"Error loading dashboard: {e}")
        return render_template('dashboard.html', error=str(e))

@app.route('/address')
def address_entry():
    """Render the address entry page"""
    return render_template('address.html')

@app.route('/address')
def address_entry():
    """Render the address entry page"""
    return render_template('address_entry.html')

@app.route('/ar-room')
def ar_room():
    """Render the AR room scanner page"""
    return render_template('ar_room.html')

@app.route('/elevate')
def elevate():
    """Render the Elevate page"""
    address_id = request.args.get('address_id')
    return render_template('elevate.html', address_id=address_id)

@app.route('/services')
def services():
    """Render the Services page"""
    address_id = request.args.get('address_id')
    return render_template('services.html', address_id=address_id)

@app.route('/diy')
def diy():
    """Render the DIY Assistant page"""
    address_id = request.args.get('address_id')
    return render_template('diy.html', address_id=address_id)

@app.route('/control')
def control():
    """Render the Control panel page"""
    address_id = request.args.get('address_id')
    return render_template('control.html', address_id=address_id)

@app.route('/settings')
def settings():
    """Render the Settings page"""
    return render_template('settings.html')

@app.route('/login')
def login():
    """Render the login page"""
    return render_template('login.html')

@app.route('/signup')
def signup():
    """Render the signup page"""
    return render_template('signup.html')

# API routes
@app.route('/api/status')
def status():
    """Returns server and DynamoDB connection status"""
    return jsonify({
        "status": "online",
        "version": "1.2.0"
    })

@app.route('/api/mapbox-token', methods=['GET'])
def mapbox_token():
    """Return Mapbox API token for client-side geocoding"""
    return jsonify({"token": MAPBOX_API_KEY})

<<<<<<< HEAD
@app.route('/api/get-addresses')
def get_addresses():
    """Return all saved addresses"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
            
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT * FROM addresses ORDER BY created_at DESC
        """)
        
        addresses = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return jsonify({"addresses": addresses})
    except Exception as e:
        logger.error(f"Error fetching addresses: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/process-address', methods=['POST'])
=======
@app.route('/api/process-address', methods=['POST'])
>>>>>>> 78aef21 (Add address entry page to property visualization platform.)
def process_address():
    """
    Process address data from the form, geocode using Mapbox, 
    generate 3D model data and save to DynamoDB
    """
    try:
        # Get form data
        data = request.json
        
        # Check if latitude and longitude are provided
        if not data.get('latitude') or not data.get('longitude'):
            return jsonify({"error": "Latitude and longitude are required"}), 400
            
        # Check if address components are provided
        if not data.get('street') or not data.get('city') or not data.get('state'):
            return jsonify({"error": "Address components are required"}), 400
        
        # Connect to the database
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
            
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Insert address into database
        cursor.execute("""
            INSERT INTO addresses 
            (street, city, state, zip, country, latitude, longitude, 
             property_type, year_built, square_footage)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING address_id
        """, (
            data.get('street', ''),
            data.get('city', ''),
            data.get('state', ''),
            data.get('zip', ''),
            data.get('country', 'USA'),
            data.get('latitude', 0),
            data.get('longitude', 0),
            data.get('propertyType', 'single_family'),
            data.get('yearBuilt', None),
            data.get('squareFootage', None)
        ))
        
        result = cursor.fetchone()
        address_id = result['address_id']
        
        # Close the database connection
        cursor.close()
        conn.close()
        
        return jsonify({
            "success": True,
            "address_id": address_id,
            "message": "Address processed successfully"
        })
    
    except Exception as e:
        logger.error(f"Error processing address: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/get-home/<int:id>')
def get_home(id):
    """Return home data by ID"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
            
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT * FROM addresses WHERE address_id = %s
        """, (id,))
        
        address = cursor.fetchone()
        
        if not address:
            cursor.close()
            conn.close()
            return jsonify({"error": "Address not found"}), 404
        
        # Get property model
        cursor.execute("""
            SELECT * FROM property_models WHERE address_id = %s
        """, (id,))
        
        property_model = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        # Combine address and property model data
        home_data = dict(address)
        if property_model:
            home_data['model_data'] = property_model.get('model_data', {})
            home_data['energy_score'] = property_model.get('energy_score', 0)
            home_data['maintenance_data'] = property_model.get('maintenance_data', {})
            home_data['weather_data'] = property_model.get('weather_data', {})
        
        return jsonify(home_data)
    except Exception as e:
        logger.error(f"Error getting home data: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/get-services')
def get_services():
    """Return list of available services"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
            
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get service categories
        cursor.execute("""
            SELECT * FROM service_categories
            ORDER BY name
        """)
        
        categories = cursor.fetchall()
        
        # For each category, get services
        for category in categories:
            cursor.execute("""
                SELECT s.*, 
                    (SELECT array_agg(json_build_object(
                        'tier_id', st.tier_id,
                        'name', st.name,
                        'description', st.description,
                        'multiplier', st.multiplier,
                        'features', st.features
                    )) FROM service_tiers st WHERE st.service_id = s.service_id)
                    AS tiers
                FROM services s
                WHERE s.category_id = %s
                ORDER BY s.name
            """, (category['category_id'],))
            
            category['services'] = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return jsonify({"categories": categories})
    except Exception as e:
        logger.error(f"Error fetching services: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/request-quote', methods=['POST'])
def request_quote():
    """Store service booking request"""
    try:
        data = request.json
        
        if not data.get('serviceId') or not data.get('addressId'):
            return jsonify({"error": "Service ID and Address ID are required"}), 400
            
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
            
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Insert the service request
        cursor.execute("""
            INSERT INTO service_requests
            (user_id, address_id, service_id, tier_id, contractor_id, 
             status, details, requested_date, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING request_id
        """, (
            1,  # Default user_id for demo
            data.get('addressId'),
            data.get('serviceId'),
            data.get('tierId'),
            data.get('contractorId'),
            'pending',
            data.get('details', ''),
            data.get('requestedDate'),
            data.get('notes', '')
        ))
        
        result = cursor.fetchone()
        request_id = result['request_id']
        
        cursor.close()
        conn.close()
        
        return jsonify({
            "success": True,
            "requestId": request_id,
            "message": "Quote request submitted successfully"
        })
    except Exception as e:
        logger.error(f"Error requesting quote: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/match-service', methods=['POST'])
def match_service():
    """Return recommended contractor for a service"""
    try:
        data = request.json
        
        if not data.get('serviceId') or not data.get('addressId'):
            return jsonify({"error": "Service ID and Address ID are required"}), 400
            
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
            
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get service and address details
        cursor.execute("""
            SELECT s.*, a.city, a.state
            FROM services s, addresses a
            WHERE s.service_id = %s AND a.address_id = %s
        """, (data.get('serviceId'), data.get('addressId')))
        
        result = cursor.fetchone()
        
        if not result:
            cursor.close()
            conn.close()
            return jsonify({"error": "Service or address not found"}), 404
            
        service_name = result['name']
        city = result['city']
        state = result['state']
        
        # Check if we have the contractor_service
        contractors = []
        try:
            if hasattr(app, 'contractor_service'):
                # Get tier level from request
                tier_level = 'professional'  # Default
                if data.get('tierId'):
                    cursor.execute("""
                        SELECT name FROM service_tiers WHERE tier_id = %s
                    """, (data.get('tierId'),))
                    tier_result = cursor.fetchone()
                    if tier_result:
                        tier_name = tier_result['name'].lower()
                        if 'standard' in tier_name:
                            tier_level = 'standard'
                        elif 'premium' in tier_name or 'professional' in tier_name:
                            tier_level = 'professional'
                        elif 'luxury' in tier_name:
                            tier_level = 'luxury'
                
                # Use the contractor service to get real contractor data
                contractors = app.contractor_service.get_contractors_by_tier(
                    service_name, city, state, tier_level, 3
                )
        except Exception as e:
            logger.error(f"Error getting contractors from service: {e}")
            # Fallback to database for contractors
        
        if not contractors:
            # Get contractors from the database as fallback
            cursor.execute("""
                SELECT c.*
                FROM contractors c
                JOIN contractor_services cs ON c.contractor_id = cs.contractor_id
                WHERE cs.service_id = %s
                LIMIT 3
            """, (data.get('serviceId'),))
            
            contractors = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return jsonify({
            "success": True,
            "contractors": contractors
        })
    except Exception as e:
        logger.error(f"Error matching service: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/login', methods=['POST'])
def api_login():
    """Handle user login"""
    data = request.json
    
    if not data or not data.get('email') or not data.get('password'):
        return jsonify({"error": "Email and password are required"}), 400
        
    # Check if the user_auth component is available
    if hasattr(user_auth, 'login'):
        success = user_auth.login(data.get('email'), data.get('password'))
        if success:
            # Set the user in session
            session['user_id'] = 1  # Default user_id for demo
            session['email'] = data.get('email')
            
            return jsonify({
                "success": True,
                "message": "Login successful"
            })
        else:
            return jsonify({
                "success": False,
                "error": "Invalid email or password"
            }), 401
    else:
        # Simplified login for demo
        session['user_id'] = 1
        session['email'] = data.get('email')
        
        return jsonify({
            "success": True,
            "message": "Login successful (demo mode)"
        })

@app.route('/api/signup', methods=['POST'])
def api_signup():
    """Handle user signup"""
    data = request.json
    
    if not data or not data.get('email') or not data.get('password'):
        return jsonify({"error": "Email and password are required"}), 400
        
    # Check if the user_auth component is available
    if hasattr(user_auth, 'register'):
        success = user_auth.register(
            data.get('email'),
            data.get('password'),
            data.get('firstName', ''),
            data.get('lastName', '')
        )
        
        if success:
            # Set the user in session
            session['user_id'] = 1  # Default user_id for demo
            session['email'] = data.get('email')
            
            return jsonify({
                "success": True,
                "message": "Signup successful"
            })
        else:
            return jsonify({
                "success": False,
                "error": "Registration failed"
            }), 400
    else:
        # Simplified signup for demo
        session['user_id'] = 1
        session['email'] = data.get('email')
        
        return jsonify({
            "success": True,
            "message": "Signup successful (demo mode)"
        })

@app.route('/api/analyze-room', methods=['POST'])
def analyze_room():
    """Analyze a room using the AI design assistant"""
    try:
        # Check if file was uploaded
        if 'image' not in request.files:
            return jsonify({"error": "No image file provided"}), 400
            
        image = request.files['image']
        room_type = request.form.get('roomType', 'living room')
        
        # Check if the design_assistant is available
        if hasattr(design_assistant, 'analyze_room'):
            results = design_assistant.analyze_room(image, room_type)
            return jsonify(results)
        else:
            # Simplified response for demo
            return jsonify({
                "room_type": room_type,
                "color_palette": ["#E0E0E0", "#D0D0D0", "#C0C0C0"],
                "existing_objects": ["sofa", "coffee table", "lamp"],
                "dimensions": {"width": "medium", "length": "medium", "height": "standard"},
                "current_style": "traditional",
                "design_opportunities": [
                    "Consider updating the wall colors for a fresh look",
                    "New lighting fixtures could enhance the ambiance",
                    "Adding accent pieces would bring visual interest"
                ]
            })
    except Exception as e:
        logger.error(f"Error analyzing room: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/design-recommendations', methods=['POST'])
def design_recommendations():
    """Get design recommendations from the AI assistant"""
    try:
        data = request.json
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
            
        room_type = data.get('roomType', 'living room')
        style = data.get('style', 'modern')
        budget = data.get('budget', 'medium')
        constraints = data.get('constraints', {})
        
        # Check if the design_assistant is available
        if hasattr(design_assistant, 'generate_recommendations'):
            results = design_assistant.generate_recommendations(room_type, style, budget, constraints)
            return jsonify(results)
        else:
            # Simplified response for demo
            return jsonify({
                "room_type": room_type,
                "style": style,
                "color_palette": ["#E0E0E0", "#D0D0D0", "#C0C0C0"],
                "materials": [
                    {"name": "Paint", "description": "Premium interior paint", "cost_range": "$30-50 per gallon"},
                    {"name": "Flooring", "description": "Engineered hardwood", "cost_range": "$3-8 per sq ft"}
                ],
                "furniture": [
                    {"name": "Sofa", "description": "Modern sectional", "cost_range": "$800-1500"},
                    {"name": "Coffee Table", "description": "Glass top with metal frame", "cost_range": "$200-400"}
                ],
                "layout_options": ["Option 1: Open concept", "Option 2: Divided spaces"],
                "estimated_costs": {"materials": "$2000-3000", "furniture": "$3000-5000", "labor": "$1000-2000"},
                "timeline": "4-6 weeks"
            })
    except Exception as e:
        logger.error(f"Error generating design recommendations: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/diy-projects')
def diy_projects():
    """Get DIY project recommendations"""
    try:
        # Get optional project type filter
        project_type = request.args.get('type')
        difficulty = request.args.get('difficulty')
        
        # Check if the diy_assistant is available
        if hasattr(diy_assistant, 'get_projects'):
            projects = diy_assistant.get_projects(project_type, difficulty)
            return jsonify({"projects": projects})
        else:
            # Simplified response for demo
            return jsonify({
                "projects": [
                    {
                        "id": 1,
                        "title": "Install a Ceiling Fan",
                        "description": "Replace an existing light fixture with a ceiling fan for improved air circulation.",
                        "difficulty": "moderate",
                        "estimated_time": "2-3 hours",
                        "materials": ["Ceiling fan kit", "Wire connectors", "Screwdriver", "Voltage tester"],
                        "steps": [
                            "Turn off power at circuit breaker",
                            "Remove existing light fixture",
                            "Install ceiling fan mounting bracket",
                            "Connect wiring",
                            "Attach fan blades and light kit"
                        ],
                        "image_url": "/static/images/ceiling_fan.jpg"
                    },
                    {
                        "id": 2,
                        "title": "Paint an Accent Wall",
                        "description": "Add a pop of color to your room with an accent wall.",
                        "difficulty": "easy",
                        "estimated_time": "3-4 hours",
                        "materials": ["Paint", "Primer", "Paintbrushes", "Roller", "Painter's tape", "Drop cloth"],
                        "steps": [
                            "Clean the wall surface",
                            "Apply painter's tape along edges",
                            "Apply primer and let dry",
                            "Apply paint in even coats",
                            "Remove tape while paint is still slightly wet"
                        ],
                        "image_url": "/static/images/accent_wall.jpg"
                    }
                ]
            })
    except Exception as e:
        logger.error(f"Error fetching DIY projects: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/diy-assistant/ask', methods=['POST'])
def diy_assistant_ask():
    """Ask a question to the DIY assistant"""
    try:
        data = request.json
        
        if not data or not data.get('question'):
            return jsonify({"error": "Question is required"}), 400
            
        question = data.get('question')
        image = data.get('image')  # Base64 encoded image if provided
        
        # Check if the diy_assistant is available
        if hasattr(diy_assistant, 'ask_question'):
            answer = diy_assistant.ask_question(question, image)
            return jsonify({"answer": answer})
        else:
            # Simplified response for demo
            return jsonify({
                "answer": "To complete that project, you'll need to start by gathering the right materials. Make sure you have proper safety equipment before beginning. The process typically takes about 3-4 hours for a beginner, and I'd rate the difficulty as moderate. Let me know if you need more specific instructions for any part of the process."
            })
    except Exception as e:
        logger.error(f"Error getting DIY assistant answer: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/verify-profile', methods=['POST'])
def verify_profile():
    """Update email and password for user profile"""
    data = request.json
    if not data:
        return jsonify({"error": "No data provided"}), 400
        
    email = data.get('email')
    password = data.get('password')
    
    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400
        
    # For demo only, in production would verify and update in database
    return jsonify({"success": True, "message": "Profile updated successfully"})

@app.route('/ar-scan', methods=['POST'])
def ar_scan():
    """Save AR scan data to database"""
    data = request.json
    if not data:
        return jsonify({"error": "No data provided"}), 400
        
    scan_data = data.get('scanData')
    home_id = data.get('homeId')
    
    if not scan_data:
        return jsonify({"error": "Scan data is required"}), 400
        
    # For demo only - would save to database in production
    scan_id = "scan_" + str(uuid.uuid4())
    
    return jsonify({
        "success": True,
        "scanId": scan_id,
        "message": "AR scan saved successfully"
    })

@app.route('/api/generate-3d-model', methods=['POST'])
def generate_3d_model():
    """Generate a 3D model for the property"""
    data = request.json
    if not data:
        return jsonify({"error": "No data provided"}), 400
        
    address_id = data.get('addressId')
    if not address_id:
        return jsonify({"error": "Address ID is required"}), 400
        
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
            
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT * FROM addresses WHERE address_id = %s
        """, (address_id,))
        
        address = cursor.fetchone()
        
        if not address:
            cursor.close()
            conn.close()
            return jsonify({"error": "Address not found"}), 404
            
        # Generate basic 3D model data - in a real implementation this would call an external service
        model_data = {
            "foundation": {
                "type": "concrete_slab",
                "dimensions": {"length": 45, "width": 30, "height": 0.5}
            },
            "floors": [
                {
                    "level": 1,
                    "rooms": [
                        {"type": "living_room", "dimensions": {"length": 20, "width": 15, "height": 9}},
                        {"type": "kitchen", "dimensions": {"length": 15, "width": 12, "height": 9}},
                        {"type": "dining_room", "dimensions": {"length": 12, "width": 12, "height": 9}},
                        {"type": "bathroom", "dimensions": {"length": 8, "width": 6, "height": 9}},
                        {"type": "hallway", "dimensions": {"length": 15, "width": 5, "height": 9}}
                    ]
                },
                {
                    "level": 2,
                    "rooms": [
                        {"type": "master_bedroom", "dimensions": {"length": 18, "width": 15, "height": 9}},
                        {"type": "bedroom", "dimensions": {"length": 12, "width": 12, "height": 9}},
                        {"type": "bedroom", "dimensions": {"length": 12, "width": 12, "height": 9}},
                        {"type": "bathroom", "dimensions": {"length": 10, "width": 8, "height": 9}},
                        {"type": "bathroom", "dimensions": {"length": 8, "width": 6, "height": 9}},
                        {"type": "hallway", "dimensions": {"length": 15, "width": 5, "height": 9}}
                    ]
                }
            ],
            "roof": {
                "type": "gable",
                "material": "asphalt_shingle",
                "pitch": 6
            },
            "exterior": {
                "material": "vinyl_siding",
                "color": "#F5F5DC"
            }
        }
            
        # Save the model data to the database
        cursor.execute("""
            INSERT INTO property_models (address_id, model_data, updated_at)
            VALUES (%s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (address_id) 
            DO UPDATE SET model_data = %s, updated_at = CURRENT_TIMESTAMP
        """, (
            address_id,
            json.dumps(model_data),
            json.dumps(model_data)
        ))
        
        cursor.close()
        conn.close()
        
        return jsonify({
            "success": True,
            "model_data": model_data,
            "message": "3D model generated successfully"
        })
    except Exception as e:
        logger.error(f"Error generating 3D model: {e}")
        return jsonify({"error": str(e)}), 500

# Start the server
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug)