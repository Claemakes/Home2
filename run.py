"""
GlassRain - Intelligent Property Platform
Main Application Entry Point
"""

import os
import json
import logging
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from werkzeug.middleware.proxy_fix import ProxyFix
import psycopg2
from psycopg2.extras import RealDictCursor
import requests

# Import GlassRain components
try:
    from enhanced_ai_design_assistant import DesignAssistant
except ImportError:
    logger.warning("Enhanced AI Design Assistant not available")
    class DesignAssistant:
        def __init__(self): pass
        
try:
    from enhanced_mapbox_integration import MapboxIntegration
except ImportError:
    logger.warning("Mapbox Integration not available")
    class MapboxIntegration:
        def __init__(self, api_key=None): pass
        
try:
    from diy_assistant import DIYAssistant
except ImportError:
    logger.warning("DIY Assistant not available")
    class DIYAssistant:
        def __init__(self, api_key=None): pass
        
try:
    from enhanced_weather_integration import weather_bp
    from weather_service import WeatherService
except ImportError:
    logger.warning("Weather Service not available")
    class WeatherService:
        def __init__(self, api_key=None): pass
    # Create an empty Blueprint for weather
    from flask import Blueprint
    weather_bp = Blueprint('weather', __name__)
        
try:
    from user_authentication import UserAuth
except ImportError:
    logger.warning("User Authentication not available")
    class UserAuth:
        def __init__(self): pass
        
try:
    from enhanced_property_data_service import EnhancedPropertyDataService
except ImportError:
    logger.warning("Enhanced Property Data Service not available")
    class EnhancedPropertyDataService:
        def __init__(self): pass
        def calculate_energy_score(self, year_built, square_footage): return 78
        def generate_3d_home_model(self, lat, lng, address): return {}

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

# Initialize Flask app
app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

# Register blueprints
app.register_blueprint(weather_bp, url_prefix='/api/weather')

# Register AI Design blueprint
try:
    from ai_design_routes import ai_design_bp
    app.register_blueprint(ai_design_bp)
    logger.info("AI Design Blueprint registered successfully")
except ImportError:
    logger.warning("AI Design Blueprint not available")

# Configure secure session management
from session_management import configure_session, login_required
app = configure_session(app)

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

# Import and run service and contractor population
try:
    from populate_services import populate_service_categories, populate_contractors
    
    # Populate services and contractors
    populate_service_categories()
    populate_contractors()
    logger.info("Service and contractor data populated successfully")
except Exception as e:
    logger.error(f"Error populating services and contractors: {e}")

# Routes
@app.route('/')
def index():
    """Render the address entry page as the landing page"""
    return render_template('address_entry.html')

@app.route('/status')
def status():
    """Return the server status"""
    return jsonify({
        'status': 'online',
        'version': '1.0.0',
        'message': 'GlassRain API is running'
    })

@app.route('/api/mapbox-token')
def mapbox_token():
    """Return Mapbox API token"""
    return jsonify({'token': os.environ.get('MAPBOX_API_KEY', '')})

@app.route('/address-entry')
def address_entry():
    """Render the address entry page"""
    return render_template('address_entry.html')

@app.route('/dashboard')
def dashboard():
    """Render the dashboard page"""
    address_id = request.args.get('address_id')
    
    if not address_id:
        # If no address is selected, redirect to address entry
        return redirect(url_for('address_entry'))
    
    try:
        # Get address and property data
        conn = get_db_connection()
        if not conn:
            return render_template('error.html', message="Database connection failed")
            
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get address details
        cursor.execute('''
            SELECT * FROM addresses WHERE address_id = %s
        ''', (address_id,))
        address = cursor.fetchone()
        
        if not address:
            return render_template('error.html', message="Address not found")
        
        # Get property model data
        cursor.execute('''
            SELECT * FROM property_models WHERE address_id = %s
        ''', (address_id,))
        model_data = cursor.fetchone()
        
        # If no model data exists, generate it
        if not model_data:
            # Generate property data
            energy_score = property_data.calculate_energy_score(
                address['year_built'], 
                address['square_footage']
            )
            
            # Get weather data
            weather_data = weather_service.get_weather(
                address['latitude'], 
                address['longitude']
            )
            
            # Create model data
            model_data = {
                'energy_score': energy_score,
                'weather': weather_data,
                'model_data': property_data.generate_3d_home_model(
                    address['latitude'], 
                    address['longitude'], 
                    f"{address['street']}, {address['city']}, {address['state']}"
                )
            }
            
            # Save the model data
            cursor.execute('''
                INSERT INTO property_models (
                    address_id, 
                    energy_score, 
                    weather_data, 
                    model_data, 
                    maintenance_data
                ) VALUES (%s, %s, %s, %s, %s)
            ''', (
                address_id, 
                energy_score, 
                json.dumps(weather_data), 
                json.dumps(model_data['model_data']), 
                json.dumps({})
            ))
        
        # Combine address and model data
        property_data = {
            **address,
            'energy_score': model_data.get('energy_score', 78),
            'weather': model_data.get('weather_data', {}),
            'model_data': model_data.get('model_data', {})
        }
        
        cursor.close()
        conn.close()
        
        return render_template('dashboard.html', property=property_data)
    except Exception as e:
        logger.error(f"Error rendering dashboard: {e}")
        return render_template('error.html', message=f"Error loading dashboard: {str(e)}")

@app.route('/elevate')
def elevate():
    """Render the Elevate tab (AI Design Assistant)"""
    address_id = request.args.get('address_id')
    return render_template('elevate.html', address_id=address_id)

@app.route('/services')
def services():
    """Render the Services tab"""
    address_id = request.args.get('address_id')
    return render_template('services.html', address_id=address_id)

@app.route('/diy')
def diy():
    """Render the DIY tab"""
    address_id = request.args.get('address_id')
    return render_template('diy.html', address_id=address_id)

@app.route('/control')
def control():
    """Render the Control tab"""
    address_id = request.args.get('address_id')
    return render_template('control.html', address_id=address_id)

@app.route('/settings')
@login_required
def settings():
    """Render the Account settings tab"""
    return render_template('settings.html')

@app.route('/api/process-address', methods=['POST'])
def process_address():
    """Process address data and save to database"""
    try:
        if not request.json:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        data = request.json
        required_fields = ['street', 'city', 'state', 'zip', 'latitude', 'longitude']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Connect to database
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
            
        cursor = conn.cursor()
        
        # Insert address into database
        cursor.execute('''
            INSERT INTO addresses (
                street, 
                city, 
                state, 
                zip, 
                country, 
                latitude, 
                longitude, 
                property_type, 
                year_built, 
                square_footage
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) 
            RETURNING address_id
        ''', (
            data['street'],
            data['city'],
            data['state'],
            data['zip'],
            data.get('country', 'USA'),
            data['latitude'],
            data['longitude'],
            data.get('property_type'),
            data.get('year_built'),
            data.get('square_footage')
        ))
        
        address_id = cursor.fetchone()[0]
        
        # If user is logged in, associate address with user
        if 'user_id' in session:
            cursor.execute('''
                INSERT INTO user_addresses (user_id, address_id, is_primary)
                VALUES (%s, %s, TRUE)
                ON CONFLICT (user_id, address_id) 
                DO UPDATE SET is_primary = TRUE
            ''', (session['user_id'], address_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Address saved successfully',
            'address_id': address_id
        })
    except Exception as e:
        logger.error(f"Error processing address: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/get-addresses')
def get_addresses():
    """Return all saved addresses"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
            
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # If user is logged in, get their addresses
        if 'user_id' in session:
            cursor.execute('''
                SELECT a.* FROM addresses a
                JOIN user_addresses ua ON a.address_id = ua.address_id
                WHERE ua.user_id = %s
                ORDER BY ua.is_primary DESC, a.created_at DESC
            ''', (session['user_id'],))
        else:
            # Otherwise, get all addresses (limited for security)
            cursor.execute('''
                SELECT * FROM addresses
                ORDER BY created_at DESC
                LIMIT 10
            ''')
        
        addresses = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return jsonify({'addresses': addresses})
    except Exception as e:
        logger.error(f"Error getting addresses: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/get-home/<int:id>')
def get_home(id):
    """Return home data by ID"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
            
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get address details
        cursor.execute('''
            SELECT * FROM addresses WHERE address_id = %s
        ''', (id,))
        address = cursor.fetchone()
        
        if not address:
            return jsonify({'error': 'Address not found'}), 404
        
        # Get property model data
        cursor.execute('''
            SELECT * FROM property_models WHERE address_id = %s
        ''', (id,))
        model_data = cursor.fetchone()
        
        # If no model data exists, generate it
        if not model_data:
            # Generate property data
            energy_score = property_data.calculate_energy_score(
                address['year_built'], 
                address['square_footage']
            )
            
            # Get weather data
            weather_data = weather_service.get_weather(
                address['latitude'], 
                address['longitude']
            )
            
            # Create model data
            home_data = {
                'energy_score': energy_score,
                'weather': weather_data,
                'model_data': property_data.generate_3d_home_model(
                    address['latitude'], 
                    address['longitude'], 
                    f"{address['street']}, {address['city']}, {address['state']}"
                )
            }
            
            # Save the model data
            cursor.execute('''
                INSERT INTO property_models (
                    address_id, 
                    energy_score, 
                    weather_data, 
                    model_data, 
                    maintenance_data
                ) VALUES (%s, %s, %s, %s, %s)
            ''', (
                id, 
                energy_score, 
                json.dumps(weather_data), 
                json.dumps(home_data['model_data']), 
                json.dumps({})
            ))
            
            conn.commit()
        else:
            # Use existing model data
            home_data = {
                'energy_score': model_data['energy_score'],
                'weather': json.loads(model_data['weather_data']) if model_data['weather_data'] else {},
                'model_data': json.loads(model_data['model_data']) if model_data['model_data'] else {}
            }
        
        # Combine address and model data
        result = {
            **address,
            **home_data
        }
        
        cursor.close()
        conn.close()
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error getting home data: {e}")
        return jsonify({'error': str(e)}), 500

# Authentication routes
@app.route('/auth/login', methods=['POST'])
def login():
    """Process login"""
    try:
        if not request.json:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        data = request.json
        email = data.get('email', '')
        password = data.get('password', '')
        
        if not email or not password:
            return jsonify({'error': 'Email and password are required'}), 400
        
        # Authenticate user
        user_id = user_auth.login(email, password)
        
        if user_id:
            # Set session
            session['user_id'] = user_id
            session['email'] = email
            
            return jsonify({
                'success': True,
                'message': 'Login successful',
                'user_id': user_id
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Invalid email or password'
            }), 401
    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/auth/register', methods=['POST'])
def register():
    """Process registration"""
    try:
        if not request.json:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        data = request.json
        email = data.get('email', '')
        password = data.get('password', '')
        first_name = data.get('first_name', '')
        last_name = data.get('last_name', '')
        
        if not email or not password:
            return jsonify({'error': 'Email and password are required'}), 400
        
        # Register user
        user_id = user_auth.register(email, password, first_name, last_name)
        
        if user_id:
            return jsonify({
                'success': True,
                'message': 'Registration successful',
                'user_id': user_id
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Email already in use'
            }), 409
    except Exception as e:
        logger.error(f"Registration error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/auth/logout')
def logout():
    """Process logout"""
    session.clear()
    return jsonify({
        'success': True,
        'message': 'Logout successful'
    })

# AI Design Assistant routes
@app.route('/api/design/analyze-room', methods=['POST'])
def analyze_room():
    """Analyze room image and return suggestions"""
    try:
        if 'image' not in request.files:
            return jsonify({'error': 'No image provided'}), 400
        
        image = request.files['image']
        room_type = request.form.get('room_type', 'living room')
        
        # Analyze room
        analysis = design_assistant.analyze_room(image, room_type)
        
        return jsonify(analysis)
    except Exception as e:
        logger.error(f"Room analysis error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/design/generate-recommendation', methods=['POST'])
def generate_recommendation():
    """Generate design recommendations based on user input"""
    try:
        if not request.json:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        data = request.json
        room_type = data.get('room_type', '')
        style = data.get('style', '')
        budget = data.get('budget', '')
        constraints = data.get('constraints', '')
        
        # Generate recommendations
        recommendations = design_assistant.generate_recommendations(
            room_type, style, budget, constraints
        )
        
        return jsonify(recommendations)
    except Exception as e:
        logger.error(f"Design recommendation error: {e}")
        return jsonify({'error': str(e)}), 500

# DIY Assistant routes
@app.route('/api/diy/get-projects', methods=['GET'])
def get_diy_projects():
    """Get DIY projects based on filters"""
    try:
        difficulty = request.args.get('difficulty')
        category = request.args.get('category')
        search = request.args.get('search')
        
        # Get projects
        projects = diy_assistant.get_projects(difficulty, category, search)
        
        return jsonify({'projects': projects})
    except Exception as e:
        logger.error(f"DIY projects error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/diy/ask-question', methods=['POST'])
def ask_diy_question():
    """Ask a DIY question and get AI response"""
    try:
        if not request.json:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        data = request.json
        question = data.get('question', '')
        
        if not question:
            return jsonify({'error': 'Question is required'}), 400
        
        # Get answer
        answer = diy_assistant.ask_question(question)
        
        return jsonify({'answer': answer})
    except Exception as e:
        logger.error(f"DIY question error: {e}")
        return jsonify({'error': str(e)}), 500

# Services routes
@app.route('/api/services/categories')
def get_service_categories():
    """Get all service categories"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
            
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute('''
            SELECT * FROM service_categories
            ORDER BY name
        ''')
        
        categories = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return jsonify({'categories': categories})
    except Exception as e:
        logger.error(f"Service categories error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/services/by-category/<int:category_id>')
def get_services_by_category(category_id):
    """Get services by category ID"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
            
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute('''
            SELECT * FROM services
            WHERE category_id = %s
            ORDER BY name
        ''', (category_id,))
        
        services = cursor.fetchall()
        
        # Get tiers for each service
        for service in services:
            cursor.execute('''
                SELECT * FROM service_tiers
                WHERE service_id = %s
                ORDER BY tier_id
            ''', (service['service_id'],))
            
            service['tiers'] = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return jsonify({'services': services})
    except Exception as e:
        logger.error(f"Services by category error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/services/contractors/<int:service_id>')
def get_contractors_by_service(service_id):
    """Get contractors by service ID"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
            
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute('''
            SELECT c.* FROM contractors c
            JOIN contractor_services cs ON c.contractor_id = cs.contractor_id
            WHERE cs.service_id = %s
            ORDER BY c.rating DESC
        ''', (service_id,))
        
        contractors = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return jsonify({'contractors': contractors})
    except Exception as e:
        logger.error(f"Contractors by service error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/services/request', methods=['POST'])
def request_service():
    """Submit a service request"""
    try:
        if not request.json:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        data = request.json
        required_fields = ['address_id', 'service_id', 'tier_id']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Connect to database
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
            
        cursor = conn.cursor()
        
        # Insert service request
        cursor.execute('''
            INSERT INTO service_requests (
                user_id, 
                address_id, 
                service_id, 
                tier_id, 
                contractor_id, 
                details
            ) VALUES (%s, %s, %s, %s, %s, %s) 
            RETURNING request_id
        ''', (
            session.get('user_id'),
            data['address_id'],
            data['service_id'],
            data['tier_id'],
            data.get('contractor_id'),
            data.get('details', '')
        ))
        
        request_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Service request submitted successfully',
            'request_id': request_id
        })
    except Exception as e:
        logger.error(f"Service request error: {e}")
        return jsonify({'error': str(e)}), 500

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(error):
    logger.error(f"Server error: {error}")
    return render_template('500.html'), 500

# Main execution
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    debug = os.environ.get('DEBUG', 'True').lower() == 'true'
    
    logger.info(f"Starting GlassRain server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=debug)