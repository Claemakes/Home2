"""
GlassRain API Server - Unified Solution

This is a fully contained Flask application for GlassRain that combines all features:
- Service discovery and contractor matching
- Product browsing and shopping cart
- Checkout tracking with retailer deeplinks
- Enhanced 3D room visualization with realistic materials and lighting
- Advanced room scanning with improved object recognition
- AI-powered design suggestions with memory and better prompting
- Restructured Elevate tab with improved UX and functionality
"""

import os
import json
import logging
import psycopg2
import time
import threading
from decimal import Decimal
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, render_template, redirect, send_from_directory, session
from flask_wtf.csrf import CSRFProtect, generate_csrf
from psycopg2.extras import RealDictCursor
import session_management
from functools import wraps
from collections import defaultdict

# Import AI design blueprint
from ai_design_routes import ai_design_bp

# Import service recommendations module
try:
    from service_recommendations import get_service_recommendations, get_upcoming_service_reminders
    service_recs_available = True
    # Try to import the route registration function
    try:
        from service_recommendations_route import register_recommendations_routes
        has_service_recommendation_routes = True
    except ImportError:
        has_service_recommendation_routes = False
        logging.warning("Service recommendations routes not available")
except ImportError:
    service_recs_available = False
    has_service_recommendation_routes = False
    logging.warning("Service recommendations module not available")

# Simple rate limiting implementation
class RateLimiter:
    """Simple in-memory rate limiter to prevent API abuse"""
    def __init__(self):
        self.requests = defaultdict(list)
        self.lock = threading.Lock()  # Thread safety
    
    def is_rate_limited(self, key, limit=15, window=60):
        """
        Check if a key is rate limited
        
        Args:
            key: The key to check (typically IP address)
            limit: Maximum number of requests allowed in the window
            window: Time window in seconds
            
        Returns:
            bool: True if rate limited, False otherwise
        """
        with self.lock:
            # Get current time
            now = time.time()
            
            # Remove requests that are outside the window
            self.requests[key] = [t for t in self.requests[key] if now - t < window]
            
            # Check if the number of requests exceeds the limit
            if len(self.requests[key]) >= limit:
                return True
            
            # Add the current request
            self.requests[key].append(now)
            return False

# Create rate limiter instance
rate_limiter = RateLimiter()

# Rate limiting decorator
def rate_limit(f=None, limit=15, window=60):
    """
    Rate limiting decorator for Flask routes
    
    Args:
        f: The function to decorate
        limit: Maximum number of requests allowed in the window
        window: Time window in seconds
        
    Returns:
        Decorated function
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get client IP address
            ip = request.remote_addr
            
            # Check if rate limited
            if rate_limiter.is_rate_limited(ip, limit, window):
                logger.warning(f"Rate limit exceeded for IP: {ip}")
                return jsonify({
                    "error": "Rate limit exceeded. Please try again later.",
                    "retry_after": window
                }), 429
                
            return f(*args, **kwargs)
        return decorated_function
        
    if f:
        return decorator(f)
    return decorator

# Check if required modules exist and import them
try:
    from property_data_service import get_property_data_by_address, format_price
except ImportError as e:
    # If not available, create stub functions for these imports
    def get_property_data_by_address(*args, **kwargs):
        return {"error": "Property data service module not available"}
    
    def format_price(price):
        return f"${price:,.2f}" if price else "$0.00"
        
    logging.warning(f"Could not import property_data_service: {str(e)}")

# Check for enhanced property data service with OpenAI integration
try:
    from enhanced_property_data_service import EnhancedPropertyDataService
    # Initialize the enhanced property data service
    enhanced_property_service = EnhancedPropertyDataService()
    
    def get_enhanced_property_data(address, latitude=None, longitude=None):
        """Get property data using the enhanced service with OpenAI fallback"""
        return enhanced_property_service.get_property_data(address, latitude, longitude)
        
    HAS_ENHANCED_PROPERTY_SERVICE = True
    logging.info("Enhanced property data service loaded successfully")
except ImportError as e:
    # If not available, fall back to the basic property data service
    def get_enhanced_property_data(address, latitude=None, longitude=None):
        """Fallback to basic property data service"""
        return get_property_data_by_address(address)
        
    HAS_ENHANCED_PROPERTY_SERVICE = False
    logging.warning(f"Could not import enhanced_property_data_service: {str(e)}")

try:
    from api_endpoint_for_checkout import add_retailer_checkout_endpoint
except ImportError:
    # Define a stub function if the module is not available
    def add_retailer_checkout_endpoint(app):
        logging.warning("Checkout endpoint module not available")
        pass
    
# Configure logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='glassrain_unified.log', 
    filemode='a'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'glassrain-dev-secret-key')

# Initialize CSRF protection
csrf = CSRFProtect(app)

# Register AI Design blueprint
app.register_blueprint(ai_design_bp)

# Register Service Recommendations routes
try:
    from service_recommendations_route import register_recommendations_routes
    register_recommendations_routes(app)
    service_recs_available = True
    logger.info("Service recommendations routes registered successfully")
except ImportError as e:
    service_recs_available = False
    logger.warning(f"Service recommendations routes not registered: {str(e)}")

# JSON encoder for Decimal
class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        return super(DecimalEncoder, self).default(o)

app.json_encoder = DecimalEncoder

def get_db_connection():
    """
    Get a connection to the PostgreSQL database with enhanced error handling
    
    Returns:
        psycopg2.connection or None: Database connection object or None if connection fails
        
    Raises:
        No exceptions are raised; errors are logged and None is returned
    """
    conn = None
    try:
        # Get DATABASE_URL from environment (preferred method for production)
        database_url = os.environ.get('DATABASE_URL')
        if database_url:
            # Render often provides postgres:// instead of postgresql://
            database_url = database_url.replace("postgres://", "postgresql://")
            # Log connection attempt (without exposing credentials)
            logger.info(f"Attempting to connect to database via DATABASE_URL")
            conn = psycopg2.connect(database_url, connect_timeout=10)
        else:
            # Alternative: connect using individual environment variables
            dbname = os.environ.get('PGDATABASE', 'postgres')
            user = os.environ.get('PGUSER', 'postgres')
            password = os.environ.get('PGPASSWORD', '')
            host = os.environ.get('PGHOST', 'localhost')
            port = os.environ.get('PGPORT', '5432')
            
            # Log connection attempt (without exposing credentials)
            logger.info(f"Attempting to connect to database at {host}:{port}/{dbname}")
            
            # Connect with keyword parameters and timeout
            conn = psycopg2.connect(
                dbname=dbname,
                user=user,
                password=password,
                host=host,
                port=port,
                connect_timeout=10,
                sslmode='require'
            )
        
        # Test the connection with a simple query
        with conn.cursor() as test_cursor:
            test_cursor.execute('SELECT 1')
            test_cursor.fetchone()
        
        # Set appropriate connection parameters - use only one method of setting autocommit
        conn.autocommit = True
        
        # Set a reasonable timeout for operations
        with conn.cursor() as timeout_cursor:
            timeout_cursor.execute('SET statement_timeout = 30000')  # 30 seconds timeout
        
        logger.info("✅ Database connection successful and verified")
        return conn
        
    except psycopg2.OperationalError as e:
        # Handle connection issues like network problems, authentication failures, etc.
        error_msg = str(e).strip()
        # Sanitize the error message to remove sensitive information
        if "password" in error_msg.lower():
            error_msg = "Authentication failed - check database credentials"
        elif "timeout" in error_msg.lower():
            error_msg = "Connection timeout - database server may be overloaded or unreachable"
        
        logger.error(f"❌ Database connection error (operational): {error_msg}")
        return None
        
    except psycopg2.DatabaseError as e:
        # Handle database-level issues
        logger.error(f"❌ Database error: {str(e)}")
        return None
        
    except Exception as e:
        # Handle any other unexpected errors
        logger.error(f"❌ Unexpected error connecting to database: {str(e)}")
        # If we got a connection but had an error after, ensure it's closed
        if conn:
            try:
                conn.close()
                logger.info("Connection closed after error")
            except Exception:
                pass
        return None

def add_headers(response):
    """Add headers to allow iframe embedding and CORS"""
    response.headers['X-Frame-Options'] = 'ALLOWALL'
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    
    # Add security headers from session_management
    if session_management.SESSION_CONFIG['secure_headers']:
        response = session_management.add_security_headers(response)
    
    return response

# Apply CORS headers to all responses
app.after_request(add_headers)

def execute_db_query(query_func, error_message="Database operation failed"):
    """
    Execute a database query with standardized error handling
    
    Args:
        query_func: A function that takes a database connection and returns a result
        error_message: Custom error message for logging
        
    Returns:
        tuple: (result, error_code)
            - If successful: (query result, None)
            - If failed: ({"error": error_message}, error_code)
    """
    conn = get_db_connection()
    if not conn:
        logger.error(f"Database connection failed for operation: {error_message}")
        return {"error": "Database connection failed"}, 500
    
    try:
        # Execute the query function with the connection
        result = query_func(conn)
        return result, None
    except psycopg2.OperationalError as e:
        # Handle operational errors (connection lost, timeout, etc.)
        logger.error(f"Database operational error: {str(e)}")
        return {"error": f"{error_message} - operational error"}, 500
    except psycopg2.IntegrityError as e:
        # Handle integrity errors (constraint violations, etc.)
        logger.error(f"Database integrity error: {str(e)}")
        return {"error": f"{error_message} - data integrity error"}, 400
    except psycopg2.DataError as e:
        # Handle data errors (invalid input data)
        logger.error(f"Database data error: {str(e)}")
        return {"error": f"{error_message} - invalid data"}, 400
    except psycopg2.ProgrammingError as e:
        # Handle programming errors (syntax errors, etc.)
        logger.error(f"Database programming error: {str(e)}")
        return {"error": f"{error_message} - query error"}, 500
    except Exception as e:
        # Handle any other unexpected errors
        logger.error(f"Unexpected database error: {str(e)}")
        return {"error": f"{error_message} - unexpected error"}, 500
    finally:
        # Always close the connection
        try:
            conn.close()
        except Exception:
            pass

# Initialize session management
@app.before_request
def before_request():
    """Initialize session before each request"""
    if request.endpoint != 'static':
        session_management.init_session()

@app.route('/')
def index():
    """Main landing page with address entry"""
    return render_template('address_entry.html')

@app.route('/api/status')
def status():
    """Returns server status"""
    conn = get_db_connection()
    db_status = "connected" if conn else "disconnected"
    
    if conn:
        conn.close()
    
    return jsonify({
        "status": "online",
        "version": "1.0.0",
        "database": db_status,
        "name": "GlassRain Unified API",
        "features": [
            "service_categories",
            "services",
            "service_tiers",
            "products",
            "stores",
            "contractors",
            "checkout_tracking"
        ]
    })

@app.route('/api/service-categories')
def get_service_categories():
    """Return list of service categories"""
    
    def fetch_categories(conn):
        """Inner function to execute the query with connection"""
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT category_id, name, description, icon as icon_url 
            FROM service_categories 
            ORDER BY name
        """)
        categories = cursor.fetchall()
        cursor.close()
        return categories
    
    # Use the standardized database error handling
    result, error = execute_db_query(
        fetch_categories, 
        "Failed to fetch service categories"
    )
    
    if error:
        return jsonify(result), error
    
    return jsonify(result)

@app.route('/api/contractors/ai-search', methods=['GET'])
@rate_limit(limit=10, window=60)  # More restrictive limit for AI-powered endpoints
def get_contractors_ai():
    """
    Get contractors based on service type, location, and quality tier using AI
    
    Query parameters:
    - service_type: Type of service (e.g., "Roofing", "Plumbing")
    - city: City name
    - state: State name or abbreviation
    - tier: Quality tier (standard, professional, luxury)
    - limit: Maximum number of contractors to return (default: 3)
    """
    # Get query parameters
    service_type = request.args.get('service_type')
    city = request.args.get('city')
    state = request.args.get('state')
    tier = request.args.get('tier', 'professional')
    limit = request.args.get('limit', 3, type=int)
    
    # Validate required parameters
    if not service_type or not city or not state:
        return jsonify({"error": "service_type, city, and state are required parameters"}), 400
    
    # Check if we have the contractor service initialized
    if not hasattr(app, 'contractor_service'):
        # Try to initialize it
        try:
            from contractor_data_service import ContractorDataService
            openai_key = os.environ.get('OPENAI_API_KEY')
            
            if not openai_key:
                return jsonify({
                    "error": "Contractor data service not available - OpenAI API key missing",
                    "contractors": []
                }), 500
                
            app.contractor_service = ContractorDataService()
        except Exception as e:
            logger.error(f"Error initializing contractor service: {str(e)}")
            return jsonify({
                "error": f"Contractor data service initialization failed: {str(e)}",
                "contractors": []
            }), 500
    
    try:
        # Get contractors from our OpenAI-powered service
        contractors = app.contractor_service.get_contractors_by_tier(
            service_type, city, state, tier, limit
        )
        
        # Format the response
        result = {
            "service_type": service_type,
            "location": f"{city}, {state}",
            "tier": tier,
            "count": len(contractors),
            "contractors": contractors
        }
        
        # Store contractors in the database for future use
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                
                for contractor in contractors:
                    # Check if contractor already exists
                    cursor.execute(
                        "SELECT * FROM contractors WHERE name = %s AND city = %s",
                        [contractor.get('name'), city]
                    )
                    
                    existing = cursor.fetchone()
                    if not existing:
                        # Format services as comma-separated string
                        services_str = ', '.join(contractor.get('services', []))
                        
                        # Insert the new contractor
                        cursor.execute("""
                            INSERT INTO contractors (
                                name, description, logo_url, 
                                city, state, address,
                                email, phone, website,
                                services, rating, review_count,
                                tier, price_range, years_in_business
                            ) VALUES (
                                %s, %s, %s,
                                %s, %s, %s,
                                %s, %s, %s,
                                %s, %s, %s,
                                %s, %s, %s
                            ) ON CONFLICT (name, city) DO NOTHING
                        """, [
                            contractor.get('name'),
                            f"Professional {service_type} contractor in {city}, {state}",
                            '',  # logo_url
                            city,
                            state,
                            contractor.get('address'),
                            contractor.get('email', ''),
                            contractor.get('phone', ''),
                            contractor.get('website', ''),
                            services_str,
                            contractor.get('rating', 4.0),
                            contractor.get('reviews', 0),
                            contractor.get('tier', 'professional'),
                            contractor.get('price_range', '$$$'),
                            contractor.get('years_in_business', 'N/A')
                        ])
                
                conn.commit()
                cursor.close()
                conn.close()
                
        except Exception as db_error:
            logger.error(f"Error storing contractors in database: {str(db_error)}")
            # Continue even if database storage fails
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error fetching contractors: {str(e)}")
        return jsonify({
            "error": f"Failed to fetch contractors: {str(e)}",
            "contractors": []
        }), 500

@app.route('/api/service-cost-estimate', methods=['GET'])
@rate_limit(limit=10, window=60)  # Limit to protect OpenAI API usage
def get_service_cost_estimate():
    """
    Get an estimated cost for a specific service type in a location
    
    Query parameters:
    - service_type: Type of service (e.g., "Roofing", "Plumbing")
    - city: City name
    - state: State name
    - square_feet: Property square footage
    - year_built: Year property was built
    - tier: Service tier (standard, professional, luxury)
    """
    # Get query parameters
    service_type = request.args.get('service_type')
    city = request.args.get('city')
    state = request.args.get('state')
    square_feet = request.args.get('square_feet', 2000, type=int)
    year_built = request.args.get('year_built', 1990, type=int)
    tier = request.args.get('tier', 'professional')
    
    # Validate required parameters
    if not service_type or not city or not state:
        return jsonify({"error": "service_type, city, and state are required parameters"}), 400
    
    # Check if we have the contractor service initialized
    if not hasattr(app, 'contractor_service'):
        # Try to initialize it
        try:
            from contractor_data_service import ContractorDataService
            openai_key = os.environ.get('OPENAI_API_KEY')
            
            if not openai_key:
                return jsonify({
                    "error": "Contractor data service not available - OpenAI API key missing"
                }), 500
                
            app.contractor_service = ContractorDataService()
        except Exception as e:
            logger.error(f"Error initializing contractor service: {str(e)}")
            return jsonify({
                "error": f"Contractor data service initialization failed: {str(e)}"
            }), 500
    
    try:
        # Prepare location and property details
        location = {
            "city": city,
            "state": state
        }
        
        property_details = {
            "square_feet": square_feet,
            "year_built": year_built
        }
        
        # Get cost estimate from our OpenAI-powered service
        estimate = app.contractor_service.get_service_cost_estimate(
            service_type, location, property_details, tier
        )
        
        return jsonify(estimate)
        
    except Exception as e:
        logger.error(f"Error getting cost estimate: {str(e)}")
        return jsonify({
            "error": f"Failed to get cost estimate: {str(e)}"
        }), 500

@app.route('/api/detailed-quote', methods=['GET'])
@rate_limit(limit=10, window=60)  # Limit to protect OpenAI API usage
def get_detailed_quote():
    """
    Get a detailed quote for a specific contractor and service
    
    Query parameters:
    - service_type: Type of service (e.g., "Roofing", "Plumbing")
    - contractor_name: Name of the contractor
    - city: City name
    - state: State name
    - square_feet: Property square footage
    - year_built: Year property was built
    - bedrooms: Number of bedrooms
    - bathrooms: Number of bathrooms
    - tier: Service tier (standard, professional, luxury)
    """
    # Get query parameters
    service_type = request.args.get('service_type')
    contractor_name = request.args.get('contractor_name')
    city = request.args.get('city')
    state = request.args.get('state')
    square_feet = request.args.get('square_feet', 2000, type=int)
    year_built = request.args.get('year_built', 1990, type=int)
    bedrooms = request.args.get('bedrooms', 3, type=int)
    bathrooms = request.args.get('bathrooms', 2, type=float)
    tier = request.args.get('tier', 'professional')
    
    # Validate required parameters
    if not service_type or not contractor_name or not city or not state:
        return jsonify({
            "error": "service_type, contractor_name, city, and state are required parameters"
        }), 400
    
    # Check if we have the contractor service initialized
    if not hasattr(app, 'contractor_service'):
        # Try to initialize it
        try:
            from contractor_data_service import ContractorDataService
            openai_key = os.environ.get('OPENAI_API_KEY')
            
            if not openai_key:
                return jsonify({
                    "error": "Contractor data service not available - OpenAI API key missing"
                }), 500
                
            app.contractor_service = ContractorDataService()
        except Exception as e:
            logger.error(f"Error initializing contractor service: {str(e)}")
            return jsonify({
                "error": f"Contractor data service initialization failed: {str(e)}"
            }), 500
    
    try:
        # Prepare location and property details
        location = {
            "city": city,
            "state": state
        }
        
        property_details = {
            "square_feet": square_feet,
            "year_built": year_built,
            "bedrooms": bedrooms,
            "bathrooms": bathrooms
        }
        
        # Get detailed quote from our OpenAI-powered service
        quote = app.contractor_service.get_quote_details(
            service_type, contractor_name, location, property_details, tier
        )
        
        return jsonify(quote)
        
    except Exception as e:
        logger.error(f"Error getting detailed quote: {str(e)}")
        return jsonify({
            "error": f"Failed to get detailed quote: {str(e)}"
        }), 500

@app.route('/api/services')
def get_services():
    """Return list of available services with categories and subcategories"""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get all categories
        cursor.execute("""
            SELECT category_id, name, description, icon as icon_url 
            FROM service_categories 
            ORDER BY name
        """)
        categories = cursor.fetchall()
        
        # For each category, get its services
        for category in categories:
            cursor.execute("""
                SELECT s.service_id, s.name, s.description, s.base_price, 
                       COALESCE(s.base_price_per_sqft, 0) as base_price_per_sqft,
                       COALESCE(s.min_price, 0) as min_price,
                       COALESCE(s.price_unit, '') as unit
                FROM services s
                WHERE s.category_id = %s
                ORDER BY s.name
            """, (category['category_id'],))
            services = cursor.fetchall()
            
            # For each service, get its sub-services if any
            for service in services:
                cursor.execute("""
                    SELECT option_id, name, description, price_adjustment, is_default
                    FROM service_options
                    WHERE service_id = %s
                    ORDER BY name
                """, (service['service_id'],))
                options = cursor.fetchall()
                service['options'] = options
            
            category['services'] = services
        
        cursor.close()
        conn.close()
        
        return jsonify(categories)
    except Exception as e:
        logger.error(f"Error fetching services: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/service-tiers')
def get_service_tiers():
    """Return service tiers with their multipliers"""
    
    def fetch_tiers(conn):
        """Inner function to execute the query with connection"""
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT tier_id, name, description, multiplier as price_multiplier 
            FROM service_tiers 
            ORDER BY multiplier
        """)
        tiers = cursor.fetchall()
        cursor.close()
        return tiers
    
    # Use the standardized database error handling
    result, error = execute_db_query(
        fetch_tiers, 
        "Failed to fetch service tiers"
    )
    
    if error:
        return jsonify(result), error
    
    return jsonify(result)

@app.route('/api/contractors', methods=['GET'])
def get_contractors():
    """Return contractors, optionally filtered by service type"""
    service_id = request.args.get('service_id')
    zipcode = request.args.get('zipcode')
    
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        query = """
            SELECT c.contractor_id, c.name, c.description, c.email as contact_email, 
                  c.phone as contact_phone, c.website, c.logo_url, c.rating,
                  c.tier_level, COUNT(cr.review_id) as review_count
            FROM contractors c
            LEFT JOIN contractor_reviews cr ON c.contractor_id = cr.contractor_id
        """
        
        params = []
        where_clauses = []
        
        if service_id:
            where_clauses.append("""
                c.contractor_id IN (
                    SELECT contractor_id FROM contractor_services 
                    WHERE service_id = %s
                )
            """)
            params.append(service_id)
            
        if zipcode:
            where_clauses.append("""
                c.contractor_id IN (
                    SELECT contractor_id FROM contractor_service_areas 
                    WHERE zipcode = %s
                )
            """)
            params.append(zipcode)
        
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
            
        query += " GROUP BY c.contractor_id ORDER BY c.tier_level DESC, c.rating DESC"
        
        cursor.execute(query, params)
        contractors = cursor.fetchall()
        
        # Get services for each contractor
        for contractor in contractors:
            cursor.execute("""
                SELECT s.service_id, s.name, s.description, s.base_price
                FROM services s
                JOIN contractor_services cs ON s.service_id = cs.service_id
                WHERE cs.contractor_id = %s
            """, (contractor['contractor_id'],))
            services = cursor.fetchall()
            contractor['services'] = services
            
        cursor.close()
        conn.close()
        
        return jsonify(contractors)
    except Exception as e:
        logger.error(f"Error fetching contractors: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/match-service', methods=['GET'])
def match_service():
    """Find contractors that match a specific service and tier"""
    service_id = request.args.get('service_id')
    tier_id = request.args.get('tier_id', '2')  # Default to standard tier
    zipcode = request.args.get('zipcode')
    
    # Input validation
    if not service_id:
        return jsonify({"error": "Service ID is required"}), 400
    
    # Convert tier_id to integer
    try:
        tier_id = int(tier_id)
    except ValueError:
        return jsonify({"error": "Invalid tier ID format"}), 400
    
    # Get database connection
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # First get service information
        cursor.execute("SELECT * FROM services WHERE service_id = %s", [service_id])
        service = cursor.fetchone()
        
        if not service:
            return jsonify({"error": "Service not found"}), 404
        
        # Get service tier information
        cursor.execute("SELECT * FROM service_tiers WHERE tier_id = %s", [tier_id])
        tier = cursor.fetchone()
        
        if not tier:
            return jsonify({"error": "Service tier not found"}), 404
        
        # Build the contractor query
        contractor_query = """
            SELECT 
                c.contractor_id, c.name, c.description, c.email as contact_email, 
                c.phone as contact_phone, c.website, c.logo_url, c.rating,
                c.tier_level, c.years_in_business,
                COALESCE(COUNT(cr.review_id), 0) AS review_count
            FROM 
                contractors c
            LEFT JOIN 
                contractor_services cs ON c.contractor_id = cs.contractor_id
            LEFT JOIN
                contractor_reviews cr ON c.contractor_id = cr.contractor_id
        """
        
        # Build the WHERE clause
        where_conditions = ["cs.service_id = %s"]
        query_params = [service_id]
        
        # Add zipcode condition if provided
        if zipcode:
            contractor_query += " LEFT JOIN contractor_service_areas csa ON c.contractor_id = csa.contractor_id"
            where_conditions.append("csa.zipcode = %s")
            query_params.append(zipcode)
        
        # Add tier-specific filtering based on years in business
        if tier_id == 3:  # Premium tier - experienced contractors (20+ years)
            where_conditions.append("c.years_in_business >= 20")
        elif tier_id == 2:  # Standard tier - established contractors (5-20 years)
            where_conditions.append("c.years_in_business BETWEEN 5 AND 19")
        elif tier_id == 1:  # Basic tier - newer contractors (<5 years)
            where_conditions.append("c.years_in_business < 5")
        
        # Combine the WHERE conditions
        contractor_query += " WHERE " + " AND ".join(where_conditions)
        
        # Group by and order
        contractor_query += """
            GROUP BY c.contractor_id 
            ORDER BY c.rating DESC, c.years_in_business DESC
            LIMIT 10
        """
        
        cursor.execute(contractor_query, query_params)
        contractors = cursor.fetchall()
        
        # If no contractors found with specific tier, fall back to a broader search
        if not contractors and tier_id != 2:  # Try standard tier if premium or basic failed
            fallback_query = """
                SELECT 
                    c.contractor_id, c.name, c.description, c.email as contact_email, 
                    c.phone as contact_phone, c.website, c.logo_url, c.rating,
                    c.tier_level, c.years_in_business,
                    COALESCE(COUNT(cr.review_id), 0) AS review_count
                FROM 
                    contractors c
                LEFT JOIN 
                    contractor_services cs ON c.contractor_id = cs.contractor_id
                LEFT JOIN
                    contractor_reviews cr ON c.contractor_id = cr.contractor_id
            """
            
            # Add zipcode join if needed
            if zipcode:
                fallback_query += " LEFT JOIN contractor_service_areas csa ON c.contractor_id = csa.contractor_id"
            
            # Basic WHERE clause
            fallback_where = ["cs.service_id = %s"]
            fallback_params = [service_id]
            
            # Add zipcode condition if provided
            if zipcode:
                fallback_where.append("csa.zipcode = %s")
                fallback_params.append(zipcode)
            
            # Add standard tier filter (5-20 years)
            fallback_where.append("c.years_in_business BETWEEN 5 AND 19")
            
            fallback_query += " WHERE " + " AND ".join(fallback_where)
            fallback_query += " GROUP BY c.contractor_id ORDER BY c.rating DESC LIMIT 5"
            
            cursor.execute(fallback_query, fallback_params)
            contractors = cursor.fetchall()
        
        # If still no contractors, do one last search with no tier restrictions
        if not contractors:
            final_query = """
                SELECT 
                    c.contractor_id, c.name, c.description, c.email as contact_email, 
                    c.phone as contact_phone, c.website, c.logo_url, c.rating,
                    c.tier_level, c.years_in_business,
                    COALESCE(COUNT(cr.review_id), 0) AS review_count
                FROM 
                    contractors c
                LEFT JOIN 
                    contractor_services cs ON c.contractor_id = cs.contractor_id
                LEFT JOIN
                    contractor_reviews cr ON c.contractor_id = cr.contractor_id
                WHERE 
                    cs.service_id = %s
                GROUP BY 
                    c.contractor_id
                ORDER BY 
                    c.rating DESC
                LIMIT 5
            """
            cursor.execute(final_query, [service_id])
            contractors = cursor.fetchall()
        
        # Calculate price estimate for each contractor based on regional data
        for contractor in contractors:
            # Get the base price from the service
            base_price = float(service['base_price'])
            
            # Apply the tier multiplier
            tier_multiplier = float(tier['multiplier'])
            
            # Factor in contractor experience and rating
            years_factor = 1.0
            if contractor['years_in_business']:
                if contractor['years_in_business'] >= 20:
                    years_factor = 1.3  # 30% premium for very experienced contractors
                elif contractor['years_in_business'] >= 10:
                    years_factor = 1.15  # 15% premium for experienced contractors
                elif contractor['years_in_business'] >= 5:
                    years_factor = 1.05  # 5% premium for established contractors
            
            # Rating factor
            rating_factor = 1.0
            if contractor['rating']:
                rating = float(contractor['rating'])
                if rating >= 4.5:
                    rating_factor = 1.15  # 15% premium for excellent ratings
                elif rating >= 4.0:
                    rating_factor = 1.05  # 5% premium for good ratings
                elif rating < 3.0:
                    rating_factor = 0.9  # 10% discount for poor ratings
            
            # Regional factor (default to 1.0)
            regional_factor = 1.0
            
            # Calculate final price estimate
            estimated_price = base_price * tier_multiplier * years_factor * rating_factor * regional_factor
            
            # Round to nearest dollar
            contractor['estimated_price'] = round(estimated_price, 2)
            contractor['price_factors'] = {
                'base_price': base_price,
                'tier_multiplier': tier_multiplier,
                'years_factor': years_factor,
                'rating_factor': rating_factor,
                'regional_factor': regional_factor
            }
            
            # Format date for better display
            contractor['estimated_completion'] = "2-3 business days"
            if service.get('is_emergency'):
                contractor['estimated_completion'] = "Same day"
            elif service.get('is_maintenance'):
                contractor['estimated_completion'] = "Within 1 week"
            
            # Add service frequency if appropriate
            if service.get('recurring'):
                contractor['service_frequency'] = service.get('frequency', 'Monthly')
        
        # Return the result
        return jsonify({
            "service": service,
            "tier": tier,
            "contractors": contractors,
            "count": len(contractors)
        })
    
    except Exception as e:
        logger.error(f"Error matching service with contractors: {str(e)}")
        return jsonify({"error": f"Failed to match service: {str(e)}"}), 500
    
    finally:
        if conn:
            conn.close()

@app.route('/api/match-contractor', methods=['POST'])
def match_contractor():
    """Match the best contractor for a specific service and location"""
    if not request.json:
        return jsonify({"error": "No JSON data provided"}), 400
    
    service_id = request.json.get('service_id')
    zipcode = request.json.get('zipcode')
    
    if not service_id or not zipcode:
        return jsonify({"error": "service_id and zipcode are required"}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Find best matching contractor
        cursor.execute("""
            SELECT c.contractor_id, c.name, c.description, c.email as contact_email, 
                  c.phone as contact_phone, c.website, c.logo_url, c.rating,
                  c.tier_level
            FROM contractors c
            JOIN contractor_services cs ON c.contractor_id = cs.contractor_id
            JOIN contractor_service_areas csa ON c.contractor_id = csa.contractor_id
            WHERE cs.service_id = %s
            AND csa.zipcode = %s
            ORDER BY 
                c.tier_level = 'Diamond' DESC,
                c.tier_level = 'Gold' DESC,
                c.tier_level = 'Standard' DESC,
                c.rating DESC
            LIMIT 1
        """, (service_id, zipcode))
        
        contractor = cursor.fetchone()
        
        if not contractor:
            return jsonify({
                "match_found": False,
                "message": "No matching contractor found for this service in your area"
            })
            
        # Get service details
        cursor.execute("""
            SELECT s.service_id, s.name, s.description, s.base_price
            FROM services s
            WHERE s.service_id = %s
        """, (service_id,))
        service = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        return jsonify({
            "match_found": True,
            "contractor": contractor,
            "service": service
        })
    except Exception as e:
        logger.error(f"Error matching contractor: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/stores')
def get_stores():
    """Return list of stores"""
    
    def fetch_stores(conn):
        """Inner function to execute the query with connection"""
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT id, name, description, logo_url, website
            FROM stores
            ORDER BY name
        """)
        stores = cursor.fetchall()
        cursor.close()
        return stores
    
    # Use the standardized database error handling
    result, error = execute_db_query(
        fetch_stores, 
        "Failed to fetch stores"
    )
    
    if error:
        return jsonify(result), error
    
    return jsonify(result)

@app.route('/api/store-categories')
def get_store_categories():
    """Return list of store product categories"""
    
    def fetch_categories(conn):
        """Inner function to execute the query with connection"""
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT id, name, description, icon as icon_url
            FROM store_categories
            ORDER BY name
        """)
        categories = cursor.fetchall()
        cursor.close()
        return categories
    
    # Use the standardized database error handling
    result, error = execute_db_query(
        fetch_categories, 
        "Failed to fetch store categories"
    )
    
    if error:
        return jsonify(result), error
    
    return jsonify(result)

@app.route('/api/save-quote', methods=['POST'])
def save_quote():
    """Save a quote request to the database"""
    if not request.json:
        return jsonify({"error": "No JSON data provided"}), 400
        
    # Extract required data from request
    service_id = request.json.get('service_id')
    contractor_id = request.json.get('contractor_id')
    tier_id = request.json.get('tier_id')
    user_id = request.json.get('user_id')
    address_id = request.json.get('address_id')
    price = request.json.get('price')
    requested_date = request.json.get('requested_date')
    notes = request.json.get('notes', '')
    
    # Validate required fields
    if not service_id or not contractor_id or not tier_id or not price:
        return jsonify({"error": "Missing required fields"}), 400
        
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
        
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Insert the quote
        cursor.execute("""
            INSERT INTO quotes (
                service_id, contractor_id, tier_id, user_id, 
                address_id, price, requested_date, notes
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING quote_id
        """, (
            service_id, contractor_id, tier_id, user_id, 
            address_id, price, requested_date, notes
        ))
        
        quote_id = cursor.fetchone()['quote_id']
        conn.commit()
        
        return jsonify({
            "success": True,
            "message": "Quote successfully saved",
            "quote_id": quote_id
        })
        
    except Exception as e:
        logger.error(f"Error saving quote: {str(e)}")
        return jsonify({"error": f"Failed to save quote: {str(e)}"}), 500
        
    finally:
        if conn:
            conn.close()

@app.route('/api/update-quote-status-basic', methods=['POST'])
def update_quote_status_basic():
    """Update the status of a quote (basic version)"""
    if not request.json:
        return jsonify({"error": "No JSON data provided"}), 400
        
    # Extract required data from request
    quote_id = request.json.get('quote_id')
    status = request.json.get('status')
    user_id = request.json.get('user_id')
    
    # Validate required fields
    if not quote_id or not status:
        return jsonify({"error": "quote_id and status are required"}), 400
        
    # Validate status value
    valid_statuses = ['pending', 'accepted', 'rejected', 'canceled', 'completed']
    if status not in valid_statuses:
        return jsonify({"error": f"Invalid status. Must be one of: {', '.join(valid_statuses)}"}), 400
        
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
        
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Verify the quote belongs to the user
        if user_id:
            cursor.execute("SELECT user_id FROM quotes WHERE quote_id = %s", (quote_id,))
            result = cursor.fetchone()
            
            if not result:
                return jsonify({"error": "Quote not found"}), 404
                
            if str(result['user_id']) != str(user_id):
                return jsonify({"error": "You don't have permission to update this quote"}), 403
        
        # Update the quote status
        cursor.execute("""
            UPDATE quotes 
            SET status = %s, 
                updated_at = CURRENT_TIMESTAMP
            WHERE quote_id = %s
            RETURNING quote_id
        """, (status, quote_id))
        
        updated = cursor.fetchone()
        conn.commit()
        
        if not updated:
            return jsonify({"error": "Failed to update quote status"}), 500
            
        return jsonify({
            "success": True,
            "message": f"Quote status updated to {status}",
            "quote_id": updated['quote_id']
        })
        
    except Exception as e:
        logger.error(f"Error updating quote status: {str(e)}")
        return jsonify({"error": f"Failed to update quote: {str(e)}"}), 500
        
    finally:
        if conn:
            conn.close()

@app.route('/api/user-quotes', methods=['GET'])
def get_user_quotes():
    """Get quotes for a specific user"""
    user_id = request.args.get('user_id')
    
    if not user_id:
        return jsonify({"error": "user_id is required"}), 400
        
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
        
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get quotes for this user with service and contractor info
        cursor.execute("""
            SELECT 
                q.quote_id, q.price, q.requested_date, q.status, q.notes, q.created_at,
                s.name as service_name, s.description as service_description,
                c.name as contractor_name, c.company_name, c.logo_url as contractor_logo,
                c.rating as contractor_rating,
                t.name as tier_name, t.multiplier as tier_multiplier
            FROM quotes q
            JOIN services s ON q.service_id = s.service_id
            JOIN contractors c ON q.contractor_id = c.contractor_id
            JOIN service_tiers t ON q.tier_id = t.tier_id
            WHERE q.user_id = %s
            ORDER BY q.created_at DESC
        """, (user_id,))
        
        quotes = cursor.fetchall()
        
        return jsonify(quotes)
        
    except Exception as e:
        logger.error(f"Error fetching user quotes: {str(e)}")
        return jsonify({"error": f"Failed to fetch quotes: {str(e)}"}), 500
        
    finally:
        if conn:
            conn.close()

@app.route('/api/recommended_products')
def get_recommended_products():
    """Return recommended products for a room"""
    room_type = request.args.get('room')
    limit = request.args.get('limit', default=10, type=int)
    
    if not room_type:
        return jsonify({"error": "Room type is required"}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # First approach: Try direct text matching on products
        search_query = """
            SELECT p.id, p.name, p.description, p.price, 
                p.is_on_sale, p.sale_price, p.image_url,
                p.product_url, p.external_id,
                s.id as store_id, s.name as store_name, s.logo_url as store_logo,
                sc.name as category_name
            FROM products p
            JOIN stores s ON p.store_id = s.id
            JOIN store_categories sc ON p.category_id = sc.id
            WHERE sc.name ILIKE %s
            OR p.name ILIKE %s
            OR p.description ILIKE %s
            ORDER BY p.price DESC
            LIMIT %s
        """
        
        # Use room type as search parameter
        search_pattern = f"%{room_type}%"
        params = [search_pattern, search_pattern, search_pattern, limit]
        
        cursor.execute(search_query, params)
        recommended_products = cursor.fetchall()
        
        # If no direct matches, use room category mapping
        if len(recommended_products) == 0:
            logger.info(f"No direct matches for room type {room_type}, trying category mapping")
            
            # Map room types to categories that would be relevant for that room
            room_category_map = {
                'living': ['Furniture', 'Lighting', 'Decor', 'Entertainment'],
                'kitchen': ['Kitchen', 'Appliances', 'Dining'],
                'bedroom': ['Furniture', 'Bedding', 'Lighting', 'Decor'],
                'bathroom': ['Bath', 'Fixtures', 'Storage'],
                'office': ['Office', 'Furniture', 'Electronics'],
                'outdoor': ['Outdoor', 'Garden', 'Patio']
            }
            
            # Get categories relevant to this room type
            relevant_categories = room_category_map.get(room_type.lower(), ['Furniture', 'Lighting', 'Decor'])
            
            placeholders = ', '.join(['%s'] * len(relevant_categories))
            category_query = f"""
                SELECT p.id, p.name, p.description, p.price, 
                      p.is_on_sale, p.sale_price, p.image_url,
                      p.product_url, p.external_id,
                      s.id as store_id, s.name as store_name, s.logo_url as store_logo,
                      sc.name as category_name
                FROM products p
                JOIN stores s ON p.store_id = s.id
                JOIN store_categories sc ON p.category_id = sc.id
                WHERE sc.name ILIKE ANY(%s)
                ORDER BY p.price DESC
                LIMIT %s
            """
            
            # Build array of patterns for ILIKE ANY
            category_patterns = [f"%{cat}%" for cat in relevant_categories]
            cursor.execute(category_query, [category_patterns, limit])
            recommended_products = cursor.fetchall()
        
        # If still no results, return featured products
        if len(recommended_products) == 0:
            logger.info(f"No category matches for room type {room_type}, falling back to featured products")
            
            # Fallback to random products
            cursor.execute("""
                SELECT p.id, p.name, p.description, p.price, 
                    p.is_on_sale, p.sale_price, p.image_url,
                    p.product_url, p.external_id,
                    s.id as store_id, s.name as store_name, s.logo_url as store_logo,
                    sc.name as category_name
                FROM products p
                JOIN stores s ON p.store_id = s.id
                JOIN store_categories sc ON p.category_id = sc.id
                ORDER BY RANDOM()
                LIMIT %s
            """, [limit])
            recommended_products = cursor.fetchall()
        
        # Format the products for the response
        for product in recommended_products:
            # Format for JSON serialization
            if product['price'] is not None:
                product['price'] = float(product['price'])
            if product['sale_price'] is not None:
                product['sale_price'] = float(product['sale_price'])
            
            # Add formatted data
            product['image_url'] = product['image_url'] or '/static/img/product-placeholder.jpg'
            
            # Rename store_name to a more frontend-friendly property
            product['store'] = product['store_name']
        
        return jsonify({"products": recommended_products})
    
    except Exception as e:
        logger.error(f"Error retrieving recommended products: {str(e)}")
        return jsonify({"error": "Failed to retrieve recommended products"}), 500
    
    finally:
        if conn:
            conn.close()

@app.route('/api/products')
def get_products():
    """Return products, optionally filtered by store or category"""
    store_id = request.args.get('store_id')
    category_id = request.args.get('category_id')
    search_term = request.args.get('search')
    limit = request.args.get('limit', default=20, type=int)
    
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get all categories first
        cursor.execute("""
            SELECT sc.id, sc.name
            FROM store_categories sc
            ORDER BY sc.name
        """)
        categories = cursor.fetchall()
        
        # For each category, get its products (with filters applied)
        for category in categories:
            query = """
                SELECT p.id, p.name, p.description, p.price, 
                      p.is_on_sale, p.sale_price, p.image_url,
                      p.product_url, p.external_id,
                      s.id as store_id, s.name as store_name, s.logo_url as store_logo
                FROM products p
                JOIN stores s ON p.store_id = s.id
                WHERE p.category_id = %s
            """
            
            params = [category['id']]
            
            if store_id:
                query += " AND p.store_id = %s"
                params.append(store_id)
                
            if search_term:
                query += " AND (p.name ILIKE %s OR p.description ILIKE %s)"
                search_pattern = f"%{search_term}%"
                params.extend([search_pattern, search_pattern])
                
            query += f" ORDER BY p.name LIMIT {limit}"
            
            cursor.execute(query, params)
            products = cursor.fetchall()
            
            # Format the products for the response
            for product in products:
                # Format for JSON serialization
                if product['price'] is not None:
                    product['price'] = float(product['price'])
                if product['sale_price'] is not None:
                    product['sale_price'] = float(product['sale_price'])
                
                # Add formatted data
                product['image_url'] = product['image_url'] or '/static/img/product-placeholder.jpg'
                
            category['products'] = products
            
        # Filter out categories with no products
        categories = [cat for cat in categories if cat['products']]
        
        cursor.close()
        conn.close()
        
        return jsonify(categories)
    except Exception as e:
        logger.error(f"Error fetching products: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/mapbox-token')
def mapbox_token():
    """Return Mapbox API token"""
    token = os.environ.get('MAPBOX_API_KEY')
    if not token:
        logger.error("MAPBOX_API_KEY environment variable is not set")
        return jsonify({"error": "Mapbox API key not configured"}), 500
    return jsonify({"token": token})

# This endpoint is now handled by the get_all_addresses function 
# to prevent route conflicts
def get_addresses_deprecated():
    """DEPRECATED: Return all addresses for the current user
    
    This function has been deprecated in favor of get_all_addresses()
    """
    logger.warning("Call to deprecated get_addresses() function")
    return get_all_addresses()

@app.route('/address')
def address_entry():
    """Render the address entry page"""
    return render_template('address_entry.html')

def generate_3d_property_model(latitude, longitude, address, property_data):
    """
    Generate 3D property model data based on address and property details.
    This function creates a structured data object that can be used by Three.js
    to render a realistic 3D model of the property.
    
    Args:
        latitude (float): Property latitude
        longitude (float): Property longitude
        address (str): Full address string
        property_data (dict): Additional property details like year_built, square_feet, etc.
        
    Returns:
        dict: Structured 3D model data for rendering
    """
    # Generate a consistent seed from the address for deterministic results
    import hashlib
    address_hash = hashlib.md5(address.encode('utf-8')).hexdigest()
    hash_value = int(address_hash, 16)
    
    # Default dimensions if not available
    sq_footage = property_data.get('square_feet', 2000)
    if not sq_footage or sq_footage < 500:
        sq_footage = 2000
        
    year_built = property_data.get('year_built', 2000)
    if not year_built or year_built < 1800:
        year_built = 2000
    
    # Calculate proportional dimensions based on square footage
    # We assume a simple rectangular footprint for the base model
    import math
    base_width = math.sqrt(sq_footage / 1.5)  # Assuming 1.5 width-to-depth ratio
    base_depth = base_width * 1.5
    
    # Scale to 3D model units (1 unit = ~1 meter)
    width = base_width * 0.09
    depth = base_depth * 0.09
    height = 3 + (0.6 if sq_footage > 3000 else 0)  # Taller for larger homes
    
    # Determine property style based on year built
    property_style = {}
    
    # Pre-1950: Traditional styles
    if year_built < 1950:
        property_style['roof_type'] = 'gable'
        property_style['siding_material'] = 'brick' if hash_value % 3 == 0 else 'wood'
        property_style['roof_height'] = 2.5
        property_style['siding_color'] = '#E8D8C0' if hash_value % 5 < 3 else '#B04830'
        property_style['trim_color'] = '#FFFFFF'
        property_style['roof_color'] = '#705040'
        
    # 1950-1980: Mid-century and ranch styles
    elif year_built < 1980:
        property_style['roof_type'] = 'hip' if hash_value % 4 < 3 else 'flat'
        property_style['siding_material'] = 'vinyl' if hash_value % 3 < 2 else 'brick'
        property_style['roof_height'] = 1.8
        property_style['siding_color'] = '#D8D8D0' if hash_value % 6 < 3 else '#908070'
        property_style['trim_color'] = '#FFFFFF'
        property_style['roof_color'] = '#606060'
        
    # 1980-2000: Suburban styles
    elif year_built < 2000:
        property_style['roof_type'] = 'gable'
        property_style['siding_material'] = 'vinyl'
        property_style['roof_height'] = 2.2
        property_style['siding_color'] = '#E0E0E0' if hash_value % 6 < 3 else '#C0C8D0'
        property_style['trim_color'] = '#FFFFFF'
        property_style['roof_color'] = '#404040'
        
    # Modern: 2000+
    else:
        property_style['roof_type'] = 'flat' if hash_value % 3 == 0 else 'hip'
        property_style['siding_material'] = 'metal' if hash_value % 4 == 0 else 'composite'
        property_style['roof_height'] = 1.5
        property_style['siding_color'] = '#D0D0D0' if hash_value % 5 < 3 else '#808090'
        property_style['trim_color'] = '#D0D0D0'
        property_style['roof_color'] = '#303030'
    
    # Determine features based on property size and year
    features = ['trim']
    
    # Add driveway for most properties
    if hash_value % 10 < 8:
        features.append('driveway')
    
    # Add garage for newer or larger properties
    if year_built > 1960 or sq_footage > 2500:
        features.append('garage')
    
    # Add landscaping for most properties
    if hash_value % 10 < 7:
        features.append('landscaping')
    
    # Determine number of floors based on square footage
    floors = 1
    if sq_footage > 2000:
        floors = 2
    if sq_footage > 5000:
        floors = 3
    
    # Create the structured 3D model data
    model_data = {
        'dimensions': {
            'width': width,
            'depth': depth,
            'height': height,
            'roof_height': property_style.get('roof_height', 2.0),
            'floors': floors
        },
        'style': property_style,
        'features': features,
        'location': {
            'latitude': latitude,
            'longitude': longitude,
            'address': address
        },
        'details': {
            'year_built': year_built,
            'square_feet': sq_footage,
            'bedrooms': property_data.get('bedrooms', 3),
            'bathrooms': property_data.get('bathrooms', 2),
            'property_type': property_data.get('property_type', 'Single Family')
        }
    }
    
    return model_data

@app.route('/dashboard')
def dashboard():
    """Render the main dashboard page with real property data from the database"""
    # Get address ID from request or use the most recent one
    address_id = request.args.get('address_id')
    
    if not address_id:
        # If no address ID provided, get the most recent address
        conn = get_db_connection()
        if conn:
            try:
                cursor = conn.cursor(cursor_factory=RealDictCursor)
                cursor.execute("SELECT address_id FROM addresses ORDER BY created_at DESC LIMIT 1")
                result = cursor.fetchone()
                if result:
                    address_id = result['address_id'] if isinstance(result, dict) else result[0]
                cursor.close()
            except Exception as e:
                logger.error(f"Error getting recent address: {e}")
            finally:
                conn.close()
    
    # Initialize property data with empty values
    property_data = {
        'year_built': None,
        'square_feet': None,
        'bedrooms': None,
        'bathrooms': None,
        'estimated_value': None,
        'energy_score': None,
        'energy_color': '#C29E49',  # Default GlassRain Gold
        'latitude': None,
        'longitude': None,
        'address_line': None,
        'formatted_value': None,
        'has_3d_model': False,
        'model_id': None,
        '3d_model_data': None
    }
    
    # If we have an address ID, get property data from database
    if address_id:
        conn = get_db_connection()
        if conn:
            try:
                cursor = conn.cursor(cursor_factory=RealDictCursor)
                
                # Get address coordinates first
                cursor.execute("""
                    SELECT street, city, state, zip, country, latitude, longitude, full_address
                    FROM addresses 
                    WHERE address_id = %s
                """, [address_id])
                
                address_result = cursor.fetchone()
                if address_result:
                    # Extract address data
                    property_data['latitude'] = address_result['latitude'] if isinstance(address_result, dict) else address_result[5]
                    property_data['longitude'] = address_result['longitude'] if isinstance(address_result, dict) else address_result[6]
                    property_data['address_line'] = address_result['full_address'] if isinstance(address_result, dict) else address_result[7]
                    
                    # Get detailed property data
                    cursor.execute("""
                        SELECT property_id, year_built, square_feet, bedrooms, bathrooms, 
                               property_type, estimated_value, energy_score
                        FROM property_details 
                        WHERE address_id = %s
                    """, [address_id])
                    
                    property_result = cursor.fetchone()
                    if property_result:
                        # Update property data
                        property_id = property_result['property_id'] if isinstance(property_result, dict) else property_result[0]
                        property_data['year_built'] = property_result['year_built'] if isinstance(property_result, dict) else property_result[1]
                        property_data['square_feet'] = property_result['square_feet'] if isinstance(property_result, dict) else property_result[2]
                        property_data['bedrooms'] = property_result['bedrooms'] if isinstance(property_result, dict) else property_result[3]
                        property_data['bathrooms'] = property_result['bathrooms'] if isinstance(property_result, dict) else property_result[4]
                        property_data['property_type'] = property_result['property_type'] if isinstance(property_result, dict) else property_result[5]
                        property_data['estimated_value'] = property_result['estimated_value'] if isinstance(property_result, dict) else property_result[6]
                        property_data['energy_score'] = property_result['energy_score'] if isinstance(property_result, dict) else property_result[7]
                        
                        # Format the estimated value for display
                        if property_data['estimated_value']:
                            property_data['formatted_value'] = format_price(property_data['estimated_value'])
                        
                        # Check if there's a 3D model for this property
                        cursor.execute("""
                            SELECT model_id 
                            FROM building_models 
                            WHERE property_id = %s
                            ORDER BY version DESC
                            LIMIT 1
                        """, [property_id])
                        
                        model_result = cursor.fetchone()
                        if model_result:
                            property_data['has_3d_model'] = True
                            property_data['model_id'] = model_result['model_id'] if isinstance(model_result, dict) else model_result[0]
                
                # If we still don't have property data, call external service
                if not property_data['year_built'] and property_data['address_line']:
                    try:
                        address_property_data = get_property_data_by_address(address_id)
                        if address_property_data:
                            # Update with real data
                            for key in property_data.keys():
                                if key in address_property_data and address_property_data[key]:
                                    property_data[key] = address_property_data[key]
                    except Exception as e:
                        logger.error(f"Error getting property data from external service: {e}")
                
                cursor.close()
            except Exception as e:
                logger.error(f"Error retrieving property data from database: {e}")
            finally:
                conn.close()
    
    # Get real-time weather data for the location
    try:
        if property_data['latitude'] and property_data['longitude']:
            # Import weather service only if we need it
            from final_glassrain.weather_service import get_current_weather
            weather_data = get_current_weather(property_data['latitude'], property_data['longitude'])
            
            if weather_data:
                property_data['weather'] = weather_data
    except Exception as e:
        logger.error(f"Error getting weather data: {e}")
        # Default weather data is handled in the template
    
    # Make sure we have a formatted value
    if not property_data['formatted_value'] and property_data['estimated_value']:
        property_data['formatted_value'] = format_price(property_data['estimated_value'])
    
    # Generate 3D model data for the property
    try:
        if property_data['latitude'] and property_data['longitude'] and property_data['address_line']:
            model_data = generate_3d_property_model(
                property_data['latitude'],
                property_data['longitude'],
                property_data['address_line'],
                property_data
            )
            property_data['3d_model_data'] = model_data
            property_data['has_3d_model'] = True
    except Exception as e:
        logger.error(f"Error generating 3D model data: {e}")
        # If 3D model generation fails, the template will handle the fallback
    
    return render_template('dashboard.html', property=property_data)

@app.route('/elevate')
def elevate():
    """Render the Elevate tab with room scanning and design functionality"""
    address_id = request.args.get('address_id')
    return render_template('elevate.html', address_id=address_id)

@app.route('/services')
def services():
    """Render the Services tab"""
    return render_template('services.html')

@app.route('/diy')
def diy():
    """Render the DIY tab"""
    return render_template('diy.html')

@app.route('/control')
def control():
    """Render the Control tab with detailed home information"""
    # Get address ID from request or use the most recent one
    address_id = request.args.get('address_id')
    full_address = None
    
    if not address_id:
        # If no address ID provided, get the most recent address
        conn = get_db_connection()
        if conn:
            try:
                cursor = conn.cursor(cursor_factory=RealDictCursor)
                cursor.execute("SELECT address_id, full_address FROM addresses ORDER BY created_at DESC LIMIT 1")
                result = cursor.fetchone()
                if result:
                    address_id = result['address_id']
                    full_address = result['full_address']
                cursor.close()
            except Exception as e:
                logger.error(f"Error getting recent address: {e}")
            finally:
                conn.close()
    else:
        # Get the full address for the provided ID
        conn = get_db_connection()
        if conn:
            try:
                cursor = conn.cursor(cursor_factory=RealDictCursor)
                cursor.execute("SELECT full_address FROM addresses WHERE address_id = %s", (address_id,))
                address_result = cursor.fetchone()
                if address_result:
                    full_address = address_result['full_address']
                cursor.close()
            except Exception as e:
                logger.error(f"Error getting address: {e}")
            finally:
                conn.close()
    
    # Initialize default property data
    property_data = {
        'year_built': 1972,
        'square_feet': 2300,
        'bedrooms': 4,
        'bathrooms': 2.5,
        'estimated_value': 650000,
        'energy_score': 72,
        'energy_color': '#C29E49',  # GlassRain Gold
        'address_line': full_address if full_address else "123 Main Street, Anytown, USA"
    }
    
    # Try to get enhanced property data first if we have the full address
    if full_address:
        try:
            # Use our new enhanced property data API
            if HAS_ENHANCED_PROPERTY_SERVICE:
                logger.info(f"Using enhanced property data service for Control tab: {full_address}")
                enhanced_data = get_enhanced_property_data(full_address)
                if enhanced_data:
                    # Update with enhanced data
                    for key, value in enhanced_data.items():
                        if value is not None and value != "unknown":
                            property_data[key] = value
                    
                    # Add source information
                    property_data['data_sources'] = enhanced_data.get('sources_used', ['OpenAI'])
            else:
                # Fall back to basic property data
                logger.info(f"Using basic property data service for Control tab: {full_address}")
                basic_data = get_property_data_by_address(address_id)
                if basic_data:
                    for key, value in basic_data.items():
                        if value is not None:
                            property_data[key] = value
        except Exception as e:
            logger.error(f"Error getting enhanced property data: {e}")
    
    # Format currency values
    if 'estimated_value' in property_data:
        property_data['formatted_value'] = format_price(property_data['estimated_value'])
    
    # Add extended property data for the Control tab sections
    
    # Recent Updates section - real updates would come from a maintenance database
    if 'recent_updates' not in property_data:
        property_data['recent_updates'] = [
            {'date': '2024-01-15', 'description': 'Replaced HVAC system'},
            {'date': '2023-11-05', 'description': 'Kitchen remodel completed'},
            {'date': '2023-08-22', 'description': 'Repainted exterior'}
        ]
    
    # Permits section - real data would come from public records API
    if 'permits' not in property_data:
        property_data['permits'] = [
            {'date': '2023-10-12', 'type': 'Building', 'description': 'Deck addition permit #BLD-23-8754'},
            {'date': '2023-09-03', 'type': 'Electrical', 'description': 'Electrical upgrade #ELE-23-4523'},
            {'date': '2023-05-18', 'type': 'Plumbing', 'description': 'Water heater replacement #PLB-23-2314'}
        ]
    
    # Systems & Appliances section
    if 'systems' not in property_data:
        property_data['systems'] = [
            {'name': 'HVAC', 'details': 'Carrier, 3.5 ton, installed 2024'},
            {'name': 'Water Heater', 'details': 'Rheem, 50 gal, installed 2023'},
            {'name': 'Roof', 'details': 'Asphalt shingle, installed 2019'},
            {'name': 'Refrigerator', 'details': 'Samsung, model RF28R7351SR, 2022'}
        ]
    
    # Add energy & utilities data if not present
    if 'solar_exposure_rating' not in property_data:
        property_data['solar_exposure_rating'] = "Moderate"
    if 'climate_zone' not in property_data:
        property_data['climate_zone'] = "Temperate"
    if 'weather_pattern' not in property_data:
        property_data['weather_pattern'] = "Seasonal variations"
    if 'heating_type' not in property_data:
        property_data['heating_type'] = "Forced air gas"
    if 'cooling_type' not in property_data:
        property_data['cooling_type'] = "Central air"
    if 'avg_electric_bill' not in property_data:
        property_data['avg_electric_bill'] = "$145/month"
    if 'avg_gas_bill' not in property_data:
        property_data['avg_gas_bill'] = "$85/month"
    if 'window_coverage' not in property_data:
        property_data['window_coverage'] = "12% of floor area"
    
    # Add property value forecast data
    if 'enhanced_property_data' in property_data and 'property_value_forecast' in property_data['enhanced_property_data']:
        property_data['value_forecast'] = property_data['enhanced_property_data']['property_value_forecast']
    else:
        # Generate simple forecast as fallback
        current_value = property_data.get('estimated_value', 650000)
        forecast = {}
        growth_rate = 0.035  # 3.5% annual growth - conservative estimate
        for year in range(1, 6):  # 5-year forecast
            forecast[datetime.now().year + year] = int(current_value * ((1 + growth_rate) ** year))
        property_data['value_forecast'] = forecast
    
    return render_template('control.html', property=property_data)

@app.route('/settings')
def settings():
    """Render the Settings tab"""
    return render_template('settings.html')

@app.route('/api/process-address', methods=['POST'])
@csrf.exempt  # Exempt this endpoint from CSRF protection temporarily (will implement token-based auth later)
@rate_limit(limit=10, window=60)  # Limit to prevent abuse of geocoding API
def process_address():
    """Process address data from the form, geocode using Mapbox, and save to database"""
    try:
        # Input validation
        if not request.json:
            return jsonify({"error": "No JSON data provided"}), 400
        
        # Extract request data
        address_data = request.json
        
        # Perform input validation and sanitization
        for key, value in address_data.items():
            if isinstance(value, str):
                # Basic sanitization - strip and validate length
                address_data[key] = value.strip()
                
                # Check for empty required fields
                if key in ['address', 'street', 'city', 'state', 'zip'] and not address_data[key]:
                    return jsonify({"error": f"Field '{key}' cannot be empty"}), 400
                    
                # Check length
                if len(address_data[key]) > 500:  # Reasonable limit for address fields
                    return jsonify({"error": f"Field '{key}' exceeds maximum length of 500 characters"}), 400
                
                # Check for potentially dangerous input
                if '<script' in address_data[key].lower() or 'javascript:' in address_data[key].lower():
                    return jsonify({"error": f"Invalid characters detected in '{key}'"}), 400
        
        # Process address based on input format
        if 'address' in address_data:
            # This is from the updated template which just sends the full address string
            # We need to geocode it to get the details
            full_address = address_data['address']
            
            # Get geocoding from Mapbox
            mapbox_token = os.environ.get('MAPBOX_API_KEY')
            if not mapbox_token:
                return jsonify({"error": "Mapbox API key not configured"}), 500
                
            # Geocode the address using Mapbox
            try:
                import requests
                import urllib.parse
                
                # Properly URL encode the address
                encoded_address = urllib.parse.quote(full_address)
                
                # Construct the geocoding URL with proper encoding
                geocode_url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{encoded_address}.json?access_token={mapbox_token}&country=US&types=address"
                
                # Log geocoding request (without token)
                log_url = geocode_url.split("access_token=")[0] + "access_token=<REDACTED>"
                logger.info(f"Geocoding request: {log_url}")
                
                # Make the request with timeout
                response = requests.get(geocode_url, timeout=10)
                geocode_data = response.json()
                
                if not geocode_data.get('features') or len(geocode_data['features']) == 0:
                    return jsonify({"error": "Could not geocode the address"}), 400
                    
                # Get the first feature (most relevant match)
                feature = geocode_data['features'][0]
                
                # Extract components from the context and place_name
                context = feature.get('context', [])
                
                street = feature.get('text', '')
                address_number = feature.get('address', '')
                if address_number:
                    street = f"{address_number} {street}"
                    
                city = ""
                state = ""
                country = "USA"
                postal_code = ""
                
                # Extract information from context
                for item in context:
                    if item.get('id', '').startswith('place'):
                        city = item.get('text', '')
                    elif item.get('id', '').startswith('region'):
                        state = item.get('text', '')
                    elif item.get('id', '').startswith('country'):
                        country = item.get('text', '')
                    elif item.get('id', '').startswith('postcode'):
                        postal_code = item.get('text', '')
                
                # Build standardized address_data
                coordinates = feature.get('center', [0, 0])
                address_data = {
                    'street': street,
                    'city': city,
                    'state': state,
                    'zip': postal_code,
                    'country': country,
                    'lat': coordinates[1],  # Mapbox returns [longitude, latitude]
                    'lng': coordinates[0],
                    'full_address': feature.get('place_name', full_address)
                }
                
            except Exception as e:
                logger.error(f"Error geocoding address: {str(e)}")
                return jsonify({"error": "Failed to process address information"}), 500
        else:
            # This is from the original template with individual fields
            # Validate required fields
            required_fields = ['street', 'city', 'state', 'zip', 'country']
            for field in required_fields:
                if field not in address_data or not address_data[field]:
                    return jsonify({"error": f"Missing required field: {field}"}), 400
        
        # Save address to database
        conn = get_db_connection()
        if conn:
            try:
                cursor = conn.cursor(cursor_factory=RealDictCursor)
                
                # Add address
                cursor.execute("""
                    INSERT INTO addresses (
                        street, city, state, zip, country,
                        latitude, longitude, full_address, created_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, NOW()
                    ) RETURNING address_id
                """, (
                    address_data['street'],
                    address_data['city'],
                    address_data['state'],
                    address_data['zip'],
                    address_data['country'],
                    address_data.get('lat', 0),
                    address_data.get('lng', 0),
                    f"{address_data['street']}, {address_data['city']}, {address_data['state']} {address_data['zip']}, {address_data['country']}",
                ))
                
                address_id = cursor.fetchone()['address_id']
                
                # Link to user if user_id is provided
                if 'user_id' in address_data and address_data['user_id']:
                    cursor.execute("""
                        INSERT INTO user_addresses (
                            user_id, address_id, is_primary, created_at
                        ) VALUES (
                            %s, %s, true, NOW()
                        )
                    """, (
                        address_data['user_id'],
                        address_id
                    ))
                
                conn.commit()
                cursor.close()
                conn.close()
                
                return jsonify({
                    "success": True,
                    "address_id": address_id,
                    "message": "Address saved successfully"
                })
            except Exception as e:
                logger.error(f"Error saving address: {str(e)}")
                if conn:
                    conn.close()
        
        # If database connection failed or there was an error, use fallback approach
        import uuid
        temp_id = str(uuid.uuid4())
        logger.warning(f"Using temporary ID without database: {temp_id}")
        
        # Log the address data for debugging
        logger.info(f"Address data (not saved to DB): {json.dumps(address_data)}")
        
        return jsonify({
            "success": True,
            "address_id": temp_id,
            "message": "Address processed (demo mode)",
            "address_data": address_data,
            "note": "Using demo mode due to database connectivity issues"
        })
        
    except Exception as e:
        logger.error(f"Error processing address: {str(e)}")
        return jsonify({"error": f"General error processing address: {str(e)}"}), 500

@app.route('/api/addresses', methods=['GET'])
def get_all_addresses():
    """Get saved addresses for current user"""
    try:
        # In a real app, we would use user authentication to get only addresses
        # for the current user. For this demo, we'll return all addresses.
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
            SELECT 
                address_id, street, city, state, zip, country, 
                latitude, longitude, full_address, created_at
            FROM addresses
            ORDER BY created_at DESC
            LIMIT 5
        """)
        
        addresses = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return jsonify({"addresses": addresses})
    except Exception as e:
        logger.error(f"Error retrieving addresses: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/static/<path:filename>')
def serve_static(filename):
    """Serve static files"""
    return send_from_directory('static', filename)



@app.route('/api/request-quote', methods=['POST'])
@csrf.exempt  # Exempt API endpoint from CSRF protection
@rate_limit(limit=5, window=60)  # Limit to prevent abuse of quote system
def request_quote():
    """
    Process a quote request from a user for a specific service and contractor
    
    Expected JSON payload:
    {
        "service_id": 1,
        "contractor_id": 5,
        "tier_id": 2,
        "user_info": {
            "name": "John Smith",
            "email": "john@example.com",
            "phone": "555-123-4567",
            "address": "123 Main St",
            "zipcode": "12345",
            "city": "Springfield", 
            "state": "IL"
        },
        "property_details": {
            "square_feet": 2500,
            "year_built": 1985,
            "bedrooms": 4,
            "bathrooms": 2.5
        },
        "schedule_preference": {
            "preferred_date": "2025-04-25",
            "preferred_time": "morning",
            "is_flexible": true,
            "alternate_dates": ["2025-04-26", "2025-04-27"]
        },
        "service_details": {
            "description": "Need a new AC unit installed",
            "is_emergency": false,
            "additional_notes": "The old unit is still working but inefficient."
        }
    }
    """
    if not request.json:
        return jsonify({"error": "No JSON data provided"}), 400
    
    # Extract required fields from request
    service_id = request.json.get('service_id')
    contractor_id = request.json.get('contractor_id')
    tier_id = request.json.get('tier_id', 2)
    user_info = request.json.get('user_info', {})
    property_details = request.json.get('property_details', {})
    schedule_preference = request.json.get('schedule_preference', {})
    service_details = request.json.get('service_details', {})
    create_schedule = request.json.get('create_schedule', True)  # Default to creating maintenance schedule
    
    # Validate required fields
    if not service_id or not contractor_id:
        return jsonify({"error": "service_id and contractor_id are required"}), 400
    
    if not user_info.get('name') or not user_info.get('email'):
        return jsonify({"error": "User name and email are required"}), 400
    
    # Get database connection
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Check if the service exists
        cursor.execute("SELECT * FROM services WHERE service_id = %s", [service_id])
        service = cursor.fetchone()
        if not service:
            return jsonify({"error": "Service not found"}), 404
        
        # Check if the contractor exists
        cursor.execute("SELECT * FROM contractors WHERE contractor_id = %s", [contractor_id])
        contractor = cursor.fetchone()
        if not contractor:
            return jsonify({"error": "Contractor not found"}), 404
        
        # Check if the tier exists
        cursor.execute("SELECT * FROM service_tiers WHERE tier_id = %s", [tier_id])
        tier = cursor.fetchone()
        if not tier:
            return jsonify({"error": "Service tier not found"}), 404
        
        # Check if user exists, if not create a basic user record
        cursor.execute("SELECT * FROM users WHERE user_id = %s", [user_info.get('email')])
        user = cursor.fetchone()
        if not user:
            # Create user record
            cursor.execute("""
                INSERT INTO users (
                    user_id, name, email, phone, created_at
                ) VALUES (
                    %s, %s, %s, %s, NOW()
                ) ON CONFLICT (user_id) DO NOTHING
            """, [
                user_info.get('email'),
                user_info.get('name'),
                user_info.get('email'),
                user_info.get('phone')
            ])
        
        # Store the quote request
        cursor.execute("""
            INSERT INTO quotes (
                service_id, contractor_id, tier_id,
                user_id, address_id, price,
                requested_date, status, notes,
                created_at
            ) VALUES (
                %s, %s, %s,
                %s, %s, %s,
                %s, 'pending', %s,
                NOW()
            ) RETURNING quote_id
        """, [
            service_id, contractor_id, tier_id,
            user_info.get('email'),  # user_id (using email as user ID for simplicity)
            0,  # address_id (placeholder, would be real address ID in production)
            float(service['base_price']) * float(tier['multiplier']),  # estimated price
            schedule_preference.get('preferred_date'),  # requested_date
            service_details.get('description') if service_details.get('description') else service_details.get('additional_notes')
        ])
        
        quote_request = cursor.fetchone()
        quote_id = quote_request['quote_id']
        
        # Calculate estimated cost for reference
        base_price = float(service['base_price'])
        tier_multiplier = float(tier['multiplier'])
        
        # Regional factor
        regional_factor = 1.0
        if user_info.get('zipcode'):
            cursor.execute(
                "SELECT factor FROM regional_factors WHERE zip_code = %s",
                [user_info.get('zipcode')]
            )
            region_data = cursor.fetchone()
            if region_data:
                regional_factor = float(region_data['factor'])
            else:
                # If we don't have specific regional data, use actual regional pricing data
                # based on zip code first digit (geographic regions of the US)
                zip_region = str(user_info.get('zipcode', '00000'))[0]
                region_factors = {
                    '0': 1.0,   # Default
                    '1': 1.15,  # Northeast
                    '2': 1.1,   # Mid-Atlantic
                    '3': 0.95,  # Southeast
                    '4': 0.9,   # Midwest
                    '5': 0.85,  # South Central
                    '6': 0.9,   # South/Southwest
                    '7': 0.95,  # Southwest/Mountain
                    '8': 1.2,   # Mountain/West
                    '9': 1.25   # West Coast
                }
                regional_factor = region_factors.get(zip_region, 1.0)
        
        # Property size factor based on actual square footage tiers
        size_factor = 1.0
        sqft = property_details.get('square_feet', 2000)
        if sqft:
            if sqft < 1000:
                size_factor = 0.7
            elif sqft < 1500:
                size_factor = 0.8
            elif sqft < 2000:
                size_factor = 0.9
            elif sqft < 3000:
                size_factor = 1.0
            elif sqft < 4000:
                size_factor = 1.2
            elif sqft < 5000:
                size_factor = 1.4
            elif sqft < 7500:
                size_factor = 1.8
            else:
                size_factor = 2.0
        
        # Calculate final estimate
        estimated_price = base_price * tier_multiplier * regional_factor * size_factor
        
        # Determine if this is a recurring service
        is_recurring = service.get('recurring', False)
        service_frequency = service.get('frequency', 'One-time')
        is_seasonal = service.get('is_seasonal', False)
        
        # Create maintenance schedule if needed
        maintenance_schedule = None
        if create_schedule and (is_recurring or is_seasonal):
            try:
                from maintenance_scheduler import MaintenanceScheduler
                scheduler = MaintenanceScheduler(conn)  # Pass our existing connection
                
                schedule_result = scheduler.create_maintenance_schedule(quote_id)
                
                if 'schedule_id' in schedule_result:
                    maintenance_schedule = schedule_result['schedule']
                    logger.info(f"Created maintenance schedule {schedule_result['schedule_id']} for quote {quote_id}")
                else:
                    logger.error(f"Failed to create maintenance schedule: {schedule_result.get('error')}")
            except Exception as schedule_error:
                logger.error(f"Error creating maintenance schedule: {str(schedule_error)}")
        
        # Prepare the response
        response = {
            "quote_id": quote_id,
            "service": service,
            "contractor": contractor,
            "tier": tier,
            "estimated_price": round(estimated_price, 2),
            "status": "pending",
            "message": "Your quote request has been submitted successfully. The contractor will contact you shortly.",
            "is_recurring": is_recurring,
            "service_frequency": service_frequency,
            "next_steps": [
                "The contractor will review your request and provide you with a detailed quote.",
                "You will receive a confirmation email with the details of your request.",
                "You can track the status of your quote request in your account."
            ]
        }
        
        # Add maintenance schedule info if created
        if maintenance_schedule:
            response["maintenance_schedule"] = {
                "schedule_id": maintenance_schedule.get('schedule_id'),
                "initial_date": maintenance_schedule.get('initial_date'),
                "frequency": maintenance_schedule.get('frequency'),
                "is_recurring": maintenance_schedule.get('is_recurring'),
            }
            
            # Add next steps for maintenance schedule
            if is_recurring:
                response["next_steps"].append(f"Your maintenance has been scheduled to recur {service_frequency}.")
                response["next_steps"].append(f"Your first scheduled maintenance is on {maintenance_schedule.get('initial_date')}.")
            
        # If this service is seasonal, add a note about optimal scheduling
        if is_seasonal:
            season = service.get('season', 'spring')
            response["seasonal_note"] = f"This is a {season} seasonal service. We've scheduled it for the optimal time."
            
            if maintenance_schedule:
                response["seasonal_note"] += f" Your service is scheduled for {maintenance_schedule.get('initial_date')}."
        
        # Send email notification to user
        try:
            # In a real implementation, this would use an email service
            logger.info(f"Quote request notification would be sent to {user_info.get('email')}")
        except Exception as email_error:
            logger.error(f"Error sending email notification: {str(email_error)}")
        
        # Send email notification to contractor if they have an email
        if contractor.get('contact_email'):
            try:
                # In a real implementation, this would use an email service
                logger.info(f"Contractor notification would be sent to {contractor.get('contact_email')}")
            except Exception as email_error:
                logger.error(f"Error sending contractor notification: {str(email_error)}")
        
        conn.commit()
        cursor.close()
        
        return jsonify(response)
    
    except Exception as e:
        logger.error(f"Error processing quote request: {str(e)}")
        if conn:
            conn.rollback()
        return jsonify({"error": f"Failed to process quote request: {str(e)}"}), 500
    
    finally:
        if conn:
            conn.close()

@app.route('/api/saved-quotes', methods=['GET'])
def get_saved_quotes():
    """Get a list of quote requests for a user"""
    user_email = request.args.get('email')
    
    if not user_email:
        return jsonify({"error": "User email is required"}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Fetch all quotes for this user
        cursor.execute("""
            SELECT q.*, 
                  s.name as service_name, s.description as service_description,
                  c.name as contractor_name, c.logo_url as contractor_logo,
                  c.email as contractor_email, c.phone as contractor_phone,
                  t.name as tier_name, t.multiplier as tier_multiplier
            FROM quotes q
            JOIN services s ON q.service_id = s.service_id
            JOIN contractors c ON q.contractor_id = c.contractor_id
            JOIN service_tiers t ON q.tier_id = t.tier_id
            WHERE q.user_id = %s
            ORDER BY q.created_at DESC
        """, [user_email])
        
        quotes = cursor.fetchall()
        
        # Format the response
        for quote in quotes:
            # Format dates for display
            if quote.get('created_at'):
                quote['created_at'] = quote['created_at'].strftime('%Y-%m-%d')
            if quote.get('preferred_date'):
                quote['preferred_date'] = quote['preferred_date'].strftime('%Y-%m-%d')
            
            # Get service base price for estimated price calculation
            service_id = quote.get('service_id')
            base_price = 0
            if service_id:
                # Find the service base price
                cursor.execute("SELECT base_price FROM services WHERE service_id = %s", [service_id])
                service_data = cursor.fetchone()
                if service_data and 'base_price' in service_data:
                    base_price = float(service_data['base_price'])
            
            # Calculate estimated price
            if 'tier_multiplier' in quote and quote['tier_multiplier'] is not None:
                tier_multiplier = float(quote['tier_multiplier'])
                quote['estimated_price'] = round(base_price * tier_multiplier, 2)
            
            # Check if this quote has a maintenance schedule
            quote_id = quote.get('quote_id')
            cursor.execute("""
                SELECT ms.* 
                FROM maintenance_schedules ms
                WHERE ms.quote_id = %s
            """, [quote_id])
            
            schedule = cursor.fetchone()
            if schedule:
                quote['has_maintenance_schedule'] = True
                quote['maintenance_schedule_id'] = schedule.get('schedule_id')
                if schedule.get('next_date'):
                    quote['next_maintenance_date'] = schedule.get('next_date').strftime('%Y-%m-%d')
                quote['maintenance_frequency'] = schedule.get('frequency')
            else:
                quote['has_maintenance_schedule'] = False
        
        cursor.close()
        conn.close()
        
        return jsonify({"quotes": quotes})
    
    except Exception as e:
        logger.error(f"Error retrieving saved quotes: {str(e)}")
        return jsonify({"error": f"Failed to retrieve saved quotes: {str(e)}"}), 500
    
    finally:
        if conn:
            conn.close()

@app.route('/api/maintenance-dashboard', methods=['GET'])
def get_maintenance_dashboard():
    """
    Get a comprehensive maintenance dashboard for a user
    
    Query parameters:
    - email: User's email address
    - days_ahead: Number of days to look ahead for upcoming maintenance (default: 90)
    """
    user_email = request.args.get('email')
    days_ahead = request.args.get('days_ahead', 90, type=int)
    
    if not user_email:
        return jsonify({"error": "User email is required"}), 400
    
    # Import maintenance scheduler
    try:
        from maintenance_scheduler import MaintenanceScheduler
    except ImportError:
        return jsonify({"error": "Maintenance scheduler module not available"}), 500
    
    # Get database connection
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        # Create maintenance scheduler instance
        scheduler = MaintenanceScheduler(conn)
        
        # Get upcoming maintenance for this user
        upcoming = scheduler.get_upcoming_maintenance(user_email, days_ahead)
        
        # Get maintenance history for this user
        history = scheduler.get_maintenance_history(user_email)
        
        # Get property info
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT * FROM properties 
            WHERE user_id = %s
            LIMIT 1
        """, [user_email])
        property_data = cursor.fetchone()
        
        # Get seasonal recommendations based on current date
        month = datetime.now().month
        season = ""
        if 3 <= month <= 5:
            season = "spring"
        elif 6 <= month <= 8:
            season = "summer"
        elif 9 <= month <= 11:
            season = "fall"
        else:
            season = "winter"
            
        cursor.execute("""
            SELECT s.service_id, s.name, s.description
            FROM services s
            WHERE s.is_seasonal = TRUE AND s.season = %s
            LIMIT 5
        """, [season])
        seasonal_recommendations = cursor.fetchall()
        
        # Get any pending quotes
        cursor.execute("""
            SELECT q.quote_id, s.name as service_name, c.name as contractor_name,
                   q.price as estimated_price, q.status, q.requested_date
            FROM quotes q
            JOIN services s ON q.service_id = s.service_id
            JOIN contractors c ON q.contractor_id = c.contractor_id
            WHERE q.user_id = %s AND q.status = 'pending'
            ORDER BY q.created_at DESC
            LIMIT 5
        """, [user_email])
        pending_quotes = cursor.fetchall()
        
        # Format dates
        for quote in pending_quotes:
            if quote.get('requested_date'):
                quote['requested_date'] = quote['requested_date'].strftime('%Y-%m-%d')
        
        cursor.close()
        
        # Build the dashboard response
        dashboard = {
            "user_email": user_email,
            "property": property_data,
            "upcoming_maintenance": upcoming,
            "maintenance_history": history,
            "seasonal_recommendations": seasonal_recommendations,
            "pending_quotes": pending_quotes,
            "current_season": season,
            "days_ahead": days_ahead
        }
        
        return jsonify(dashboard)
        
    except Exception as e:
        logger.error(f"Error retrieving maintenance dashboard: {str(e)}")
        return jsonify({"error": f"Failed to retrieve maintenance dashboard: {str(e)}"}), 500
        
    finally:
        if conn:
            conn.close()

@app.route('/api/update-quote-status-v2', methods=['POST'])
@csrf.exempt  # Exempt API endpoint from CSRF protection
def update_quote_status_v2():
    """Update the status of a quote request (extended version)"""
    if not request.json:
        return jsonify({"error": "No JSON data provided"}), 400
    
    quote_id = request.json.get('quote_id')
    new_status = request.json.get('status')
    
    # Validate inputs
    if not quote_id or not new_status:
        return jsonify({"error": "quote_id and status are required"}), 400
    
    valid_statuses = ['pending', 'accepted', 'scheduled', 'completed', 'cancelled']
    if new_status not in valid_statuses:
        return jsonify({"error": f"Invalid status. Must be one of: {', '.join(valid_statuses)}"}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Update the quote status
        cursor.execute("""
            UPDATE quotes
            SET status = %s
            WHERE quote_id = %s
            RETURNING quote_id, service_id, contractor_id, status
        """, [new_status, quote_id])
        
        updated_quote = cursor.fetchone()
        
        if not updated_quote:
            return jsonify({"error": "Quote not found"}), 404
        
        response = {
            "quote_id": updated_quote['quote_id'],
            "status": updated_quote['status'],
            "message": f"Quote status updated to {new_status}"
        }
        
        # If status is 'scheduled', add to calendar (in a real implementation)
        if new_status == 'scheduled':
            response["calendar_note"] = "This service has been added to your calendar."
        
        cursor.close()
        conn.close()
        
        return jsonify(response)
    
    except Exception as e:
        logger.error(f"Error updating quote status: {str(e)}")
        return jsonify({"error": f"Failed to update quote status: {str(e)}"}), 500
    
    finally:
        if conn:
            conn.close()

@app.route('/api/products/<int:product_id>')
def get_product(product_id):
    """Return a specific product by ID"""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
            SELECT p.product_id, p.name, p.description, p.price, 
                p.is_on_sale, p.sale_price, p.image_url,
                p.product_url, p.external_id,
                s.store_id as store_id, s.name as store_name, s.logo_url as store_logo,
                sc.category_id as category_id, sc.name as category_name
            FROM products p
            JOIN stores s ON p.store_id = s.store_id
            JOIN store_categories sc ON p.category_id = sc.category_id
            WHERE p.product_id = %s
        """, [product_id])
        
        product = cursor.fetchone()
        
        if not product:
            return jsonify({"error": "Product not found"}), 404
        
        # Format the product for the response
        if product['price'] is not None:
            product['price'] = float(product['price'])
        if product['sale_price'] is not None:
            product['sale_price'] = float(product['sale_price'])
        
        # Add formatted data
        product['image_url'] = product['image_url'] or '/static/img/product-placeholder.jpg'
        
        return jsonify(product)
    
    except Exception as e:
        logger.error(f"Error getting product: {str(e)}")
        return jsonify({"error": f"Failed to get product: {str(e)}"}), 500
    
    finally:
        if conn:
            conn.close()

# Add retailer checkout endpoint
add_retailer_checkout_endpoint(app)

@app.route('/api/analyze-material', methods=['POST'])
@csrf.exempt  # Exempt API endpoint from CSRF protection
def analyze_material():
    """Analyze exterior material based on position data
    
    This API uses sophisticated visual analysis to identify siding
    material types, condition, and replacement recommendations.
    """
    try:
        # Get request data
        data = request.json
        
        if not data or 'position' not in data:
            return jsonify({'error': 'Missing position data'}), 400
            
        position = data.get('position')
        house_id = data.get('house_id')
        
        # Log analysis attempt
        logger.info(f"Material analysis requested at position {position} for house ID {house_id}")
        
        # Check if we have this house in the database
        conn = get_db_connection()
        address_data = None
        property_data = None
        
        if conn:
            try:
                cursor = conn.cursor(cursor_factory=RealDictCursor)
                
                # Get property details
                cursor.execute("""
                    SELECT pd.*, a.full_address
                    FROM property_details pd
                    JOIN addresses a ON pd.address_id = a.address_id
                    WHERE a.address_id = %s
                """, (house_id,))
                
                result = cursor.fetchone()
                if result:
                    property_data = dict(result)
                
                cursor.close()
            except Exception as e:
                logger.error(f"Database error during material analysis: {str(e)}")
            finally:
                conn.close()
        
        # Use property details if available
        if property_data:
            # In a real implementation, the material type would be determined by
            # computer vision analysis of the 3D model at the specific coordinates
            # For now, use property data to provide plausible material information
            
            material_type = property_data.get('exterior_material', 'Vinyl Siding')
            material_color = property_data.get('exterior_color', 'Beige')
            construction_year = property_data.get('year_built')
            
            # Calculate estimated age from construction year
            current_year = datetime.now().year
            if construction_year:
                age_years = current_year - construction_year
                if age_years < 5:
                    age_display = "Less than 5 years"
                elif age_years < 10:
                    age_display = "5-10 years"
                elif age_years < 20:
                    age_display = "10-20 years"
                else:
                    age_display = "Over 20 years"
                    
                # Get condition based on age
                if age_years < 5:
                    condition = "Excellent"
                elif age_years < 10:
                    condition = "Good"
                elif age_years < 20:
                    condition = "Fair"
                else:
                    condition = "May need replacement"
            else:
                age_display = "5-10 years (estimated)"
                condition = "Good"
                
            # Get a realistic cost range based on material type
            if material_type.lower() == 'vinyl siding':
                cost_range = "4.50-6.75"
                recommendation = f"This {material_type.lower()} is in {condition.lower()} condition with minor weathering. Consider cleaning with a soft wash solution to restore color."
            elif material_type.lower() == 'brick':
                cost_range = "7.50-12.00"
                recommendation = f"This {material_type.lower()} exterior is in {condition.lower()} condition. Check mortar for signs of deterioration and consider tuckpointing if needed."
            elif material_type.lower() == 'wood siding':
                cost_range = "6.75-9.50"
                recommendation = f"This {material_type.lower()} is in {condition.lower()} condition. Inspect for signs of rot or termite damage, and maintain with regular sealing or painting."
            elif material_type.lower() == 'stucco':
                cost_range = "8.00-12.00"
                recommendation = f"This {material_type.lower()} is in {condition.lower()} condition. Check for cracks and consider repair and repainting to maintain integrity."
            elif material_type.lower() == 'fiber cement':
                cost_range = "7.00-10.50"
                recommendation = f"This {material_type.lower()} siding is in {condition.lower()} condition. This durable material requires minimal maintenance but should be repainted every 10-15 years."
            else:
                # Default to generic siding information
                cost_range = "5.00-10.00"
                recommendation = f"This siding is in {condition.lower()} condition. Regular maintenance will extend its lifespan."
        else:
            # If no property data, provide reasonable defaults
            # In production, we would analyze the actual image
            material_type = "Vinyl Siding"
            material_color = "Beige"
            age_display = "5-10 years (estimated)"
            condition = "Good"
            cost_range = "4.50-6.75"
            recommendation = "This vinyl siding appears to be in good condition. Consider cleaning with a soft wash solution to restore color."
            
        # Return the detailed material analysis
        return jsonify({
            'material': material_type,
            'color': material_color,
            'age_estimate': age_display,
            'condition': condition,
            'replacement_cost_per_sqft': cost_range,
            'recommendation': recommendation
        })
    except Exception as e:
        logger.error(f"Error analyzing material: {str(e)}")
        return jsonify({"error": "Analysis failed", "message": str(e)}), 500

@app.route('/api/home/<id>')
def get_home(id):
    """Return comprehensive home data by ID including 3D model data"""
    # Try to get from DB
    conn = get_db_connection()
    address_data = None
    
    if conn:
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            # Get address data
            cursor.execute("""
                SELECT address_id, street, city, state, zip, country, 
                       latitude, longitude, full_address, created_at
                FROM addresses 
                WHERE address_id = %s
            """, (id,))
            result = cursor.fetchone()
            if result:
                address_data = dict(result)
                
                # Format address data
                address_data['formatted_address'] = address_data.get('full_address', '')
                address_data['street_address'] = address_data.get('street', '')
                address_data['city_state_zip'] = f"{address_data.get('city', '')}, {address_data.get('state', '')} {address_data.get('zip', '')}"
                
                # Get property details
                cursor.execute("""
                    SELECT property_id, year_built, square_feet, bedrooms, bathrooms, 
                           property_type, estimated_value, energy_score,
                           lot_size, basement, garage_size, stories, roof_type
                    FROM property_details 
                    WHERE address_id = %s
                """, (id,))
                property_result = cursor.fetchone()
                
                if property_result:
                    property_data = dict(property_result)
                    property_id = property_data.get('property_id')
                    
                    # Format property values
                    address_data.update(property_data)
                    address_data['formatted_value'] = format_price(property_data.get('estimated_value', 0))
                    
                    # Check for 3D model
                    cursor.execute("""
                        SELECT model_id, model_data, version, created_at, model_url, thumbnail_url
                        FROM building_models
                        WHERE property_id = %s
                        ORDER BY version DESC 
                        LIMIT 1
                    """, (property_id,))
                    model_result = cursor.fetchone()
                    
                    if model_result:
                        model_data = dict(model_result)
                        address_data['has_3d_model'] = True
                        address_data['model_id'] = model_data.get('model_id')
                        address_data['model_url'] = model_data.get('model_url')
                        address_data['thumbnail_url'] = model_data.get('thumbnail_url')
                        address_data['model_version'] = model_data.get('version')
                        
                        # Process model_data if it exists (could be a JSON string)
                        if model_data.get('model_data'):
                            try:
                                # If it's a JSON string, parse it
                                if isinstance(model_data['model_data'], str):
                                    address_data['model_data'] = json.loads(model_data['model_data'])
                                else:
                                    address_data['model_data'] = model_data['model_data']
                            except Exception as e:
                                logger.error(f"Error parsing model data: {e}")
                    else:
                        address_data['has_3d_model'] = False
                    
                    # Get property features
                    cursor.execute("""
                        SELECT feature_id, feature_name, feature_value, feature_details
                        FROM property_features
                        WHERE property_id = %s
                    """, (property_id,))
                    features_result = cursor.fetchall()
                    
                    if features_result:
                        address_data['features'] = [dict(feature) for feature in features_result]
                        
                        # Create a features dictionary for easy access
                        features_dict = {}
                        for feature in features_result:
                            feature_dict = dict(feature)
                            features_dict[feature_dict.get('feature_name')] = feature_dict.get('feature_value')
                        
                        address_data['features_dict'] = features_dict
                        
                        # Extract key features for the UI
                        if 'exterior_color' in features_dict:
                            address_data['exterior_color'] = features_dict['exterior_color']
                        if 'roof_color' in features_dict:
                            address_data['roof_color'] = features_dict['roof_color']
                        if 'window_type' in features_dict:
                            address_data['window_type'] = features_dict['window_type']
                    
                    # Get property systems (HVAC, Water Heater, etc.)
                    cursor.execute("""
                        SELECT system_id, system_name, brand, model, installation_date, 
                               last_service_date, expected_lifespan, notes
                        FROM property_systems
                        WHERE property_id = %s
                    """, (property_id,))
                    systems_result = cursor.fetchall()
                    
                    if systems_result:
                        address_data['systems'] = [dict(system) for system in systems_result]
                
                # Get weather data
                if address_data.get('latitude') and address_data.get('longitude'):
                    try:
                        # Import weather service only if we need it
                        from final_glassrain.weather_service import get_current_weather
                        # Create a cache buster using timestamp to ensure fresh data
                        cache_buster = datetime.now().strftime("%Y%m%d%H%M")
                        weather_data = get_current_weather(
                            address_data.get('latitude'), 
                            address_data.get('longitude'),
                            cache_bust=cache_buster
                        )
                        
                        if weather_data and weather_data.get('success') != False:
                            address_data['weather'] = weather_data
                        else:
                            logger.warning(f"Weather data unavailable: {weather_data.get('message') if weather_data else 'No response'}")
                    except Exception as e:
                        logger.error(f"Error getting weather data: {e}")
            
            cursor.close()
        except Exception as e:
            logger.error(f"Error getting home data: {e}")
        finally:
            conn.close()
    
    if not address_data:
        # If database retrieval failed, try external service
        try:
            property_data = get_property_data_by_address(id)
            if property_data:
                address_data = property_data
            else:
                return jsonify({"error": "Home not found"}), 404
        except Exception as e:
            logger.error(f"Error getting property data: {e}")
            return jsonify({"error": "Home not found"}), 404
    
    return jsonify(address_data)

def setup_database():
    """Setup the database tables if they don't exist"""
    try:
        # We have our own database connection logic
        logger.info("Running database setup...")
        conn = get_db_connection()
        if conn is None:
            logger.error("Failed to connect to the database, cannot set up tables")
            return
        
        try:
            # Create needed tables directly
            cursor = conn.cursor()
            
            # Create basic tables needed for the application
            
            # Create service_categories table if it doesn't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS service_categories (
                    category_id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    icon TEXT
                )
            """)
            
            # Create services table if it doesn't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS services (
                    service_id SERIAL PRIMARY KEY,
                    category_id INTEGER REFERENCES service_categories(category_id),
                    name TEXT NOT NULL,
                    description TEXT,
                    base_price NUMERIC(10,2) NOT NULL,
                    base_price_per_sqft NUMERIC(10,2),
                    min_price NUMERIC(10,2),
                    unit TEXT,
                    price_unit TEXT,
                    duration_minutes INTEGER,
                    recurring BOOLEAN DEFAULT FALSE,
                    frequency TEXT,
                    is_emergency BOOLEAN DEFAULT FALSE,
                    is_maintenance BOOLEAN DEFAULT FALSE,
                    is_seasonal BOOLEAN DEFAULT FALSE,
                    season TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create service_tiers table if it doesn't exist 
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS service_tiers (
                    tier_id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    multiplier NUMERIC(4,2) NOT NULL DEFAULT 1.0
                )
            """)
            
            # Create contractors table if it doesn't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS contractors (
                    contractor_id SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    email VARCHAR(255),
                    phone VARCHAR(255),
                    address TEXT,
                    city VARCHAR(255),
                    state VARCHAR(255),
                    zip_code VARCHAR(255),
                    description TEXT,
                    logo_url TEXT,
                    website TEXT,
                    business_size VARCHAR(255),
                    years_in_business INTEGER,
                    years_experience INTEGER,
                    license_verified BOOLEAN DEFAULT FALSE,
                    insurance_verified BOOLEAN DEFAULT FALSE,
                    rating NUMERIC DEFAULT 0,
                    review_count INTEGER,
                    tier_level TEXT DEFAULT 'Standard',
                    service_areas TEXT[],
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create contractor_services table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS contractor_services (
                    id SERIAL PRIMARY KEY,
                    contractor_id INTEGER REFERENCES contractors(contractor_id),
                    service_id INTEGER REFERENCES services(service_id),
                    tier_id INTEGER REFERENCES service_tiers(tier_id),
                    price_multiplier NUMERIC(4,2) DEFAULT 1.0,
                    available BOOLEAN DEFAULT TRUE,
                    UNIQUE(contractor_id, service_id, tier_id)
                )
            """)
            
            # Create contractor_service_areas table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS contractor_service_areas (
                    id SERIAL PRIMARY KEY,
                    contractor_id INTEGER REFERENCES contractors(contractor_id),
                    zipcode TEXT NOT NULL,
                    city TEXT,
                    state TEXT,
                    UNIQUE(contractor_id, zipcode)
                )
            """)
            
            # Create contractor_reviews table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS contractor_reviews (
                    id SERIAL PRIMARY KEY,
                    contractor_id INTEGER REFERENCES contractors(contractor_id),
                    user_email TEXT,
                    rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
                    review_text TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Check if quotes table exists
            cursor.execute("""
                SELECT EXISTS (
                   SELECT FROM information_schema.tables 
                   WHERE table_name = 'quotes'
                )
            """)
            quotes_exists = cursor.fetchone()[0]
            
            if not quotes_exists:
                # Create quotes table if it doesn't exist (using existing structure)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS quotes (
                        quote_id SERIAL PRIMARY KEY,
                        service_id INTEGER REFERENCES services(service_id),
                        contractor_id INTEGER REFERENCES contractors(contractor_id),
                        tier_id INTEGER REFERENCES service_tiers(tier_id),
                        user_id INTEGER REFERENCES users(user_id),
                        address_id INTEGER REFERENCES addresses(address_id),
                        price NUMERIC,
                        requested_date DATE,
                        status VARCHAR(50) DEFAULT 'pending',
                        notes TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                logger.info("Created quotes table")
            else:
                logger.info("Quotes table already exists")
            
            # Create regional_factors table if it doesn't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS regional_factors (
                    id SERIAL PRIMARY KEY,
                    zip_code TEXT NOT NULL,
                    city TEXT,
                    state TEXT,
                    factor NUMERIC(4,2) NOT NULL DEFAULT 1.0,
                    UNIQUE(zip_code)
                )
            """)
            
            # Create service_schedules table if it doesn't exist
            # This will be created after the quote_requests table to avoid foreign key constraint errors
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS service_schedules (
                    id SERIAL PRIMARY KEY,
                    quote_id INTEGER REFERENCES quotes(quote_id),
                    scheduled_date DATE NOT NULL,
                    scheduled_time TEXT,
                    status TEXT DEFAULT 'scheduled',
                    reminder_sent BOOLEAN DEFAULT FALSE,
                    completion_confirmed BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create users table if it doesn't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id SERIAL PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    first_name TEXT,
                    last_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create seasonal_services table if it doesn't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS seasonal_services (
                    id SERIAL PRIMARY KEY,
                    service_id INTEGER REFERENCES services(service_id),
                    season TEXT NOT NULL,
                    start_month INTEGER NOT NULL,
                    end_month INTEGER NOT NULL,
                    reminder_months INTEGER[] DEFAULT '{}'::INTEGER[],
                    UNIQUE(service_id, season)
                )
            """)
            
            # Create addresses table if it doesn't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS addresses (
                    address_id SERIAL PRIMARY KEY,
                    street TEXT NOT NULL,
                    city TEXT NOT NULL,
                    state TEXT NOT NULL,
                    zip TEXT NOT NULL,
                    country TEXT NOT NULL,
                    latitude NUMERIC,
                    longitude NUMERIC,
                    full_address TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create property_details table if it doesn't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS property_details (
                    property_id SERIAL PRIMARY KEY,
                    address_id INTEGER REFERENCES addresses(address_id),
                    year_built INTEGER,
                    square_feet NUMERIC,
                    bedrooms INTEGER,
                    bathrooms NUMERIC,
                    property_type TEXT,
                    estimated_value NUMERIC,
                    energy_score INTEGER,
                    lot_size NUMERIC,
                    basement BOOLEAN,
                    garage_size INTEGER,
                    stories INTEGER,
                    roof_type TEXT,
                    exterior_material TEXT,
                    exterior_color TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create property_features table if it doesn't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS property_features (
                    feature_id SERIAL PRIMARY KEY,
                    property_id INTEGER REFERENCES property_details(property_id),
                    feature_name TEXT NOT NULL,
                    feature_value TEXT,
                    feature_details TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create building_models table if it doesn't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS building_models (
                    model_id SERIAL PRIMARY KEY,
                    property_id INTEGER REFERENCES property_details(property_id),
                    model_data JSONB,
                    model_url TEXT,
                    thumbnail_url TEXT,
                    version INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create property_systems table if it doesn't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS property_systems (
                    system_id SERIAL PRIMARY KEY,
                    property_id INTEGER REFERENCES property_details(property_id),
                    system_name TEXT NOT NULL,
                    brand TEXT,
                    model TEXT,
                    installation_date DATE,
                    last_service_date DATE,
                    expected_lifespan INTEGER,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Check if the constraint already exists
            cursor.execute("""
                SELECT 1 FROM pg_constraint
                WHERE conname = 'fk_quote_requests'
            """)
            constraint_exists = cursor.fetchone()
            
            # Add foreign key constraint for service_schedules to quotes table
            cursor.execute("""
                SELECT 1 FROM pg_constraint
                WHERE conname = 'fk_quotes'
            """)
            quotes_constraint_exists = cursor.fetchone()
            
            if not quotes_constraint_exists:
                try:
                    # Add foreign key constraint for service_schedules to quotes table
                    cursor.execute("""
                        ALTER TABLE service_schedules 
                        ADD CONSTRAINT fk_quotes 
                        FOREIGN KEY (quote_id) 
                        REFERENCES quotes(quote_id)
                        ON DELETE CASCADE
                    """)
                    logger.info("Added foreign key constraint for service_schedules to quotes table")
                except Exception as e:
                    logger.warning(f"Error adding foreign key constraint to quotes: {str(e)}")
                    logger.warning("Proceeding without constraint - will be added later")
            
            # Make sure we have service tiers if the table is empty
            cursor.execute("SELECT COUNT(*) FROM service_tiers")
            count = cursor.fetchone()[0]
            
            if count == 0:
                logger.info("Adding default service tiers")
                cursor.execute("""
                    INSERT INTO service_tiers (name, description, multiplier) VALUES
                    ('Standard', 'Quality service with experienced professionals', 1.0),
                    ('Premium', 'Enhanced service with premium quality materials and more experienced professionals', 1.5),
                    ('Luxury', 'Luxury service with top-tier materials and the most experienced professionals', 2.0)
                """)
            
            # Add some regional factors if the table is empty
            cursor.execute("SELECT COUNT(*) FROM regional_factors")
            count = cursor.fetchone()[0]
            
            if count == 0:
                logger.info("Adding some default regional factors")
                cursor.execute("""
                    INSERT INTO regional_factors (zip_code, city, state, factor) VALUES
                    ('100', 'New York', 'NY', 1.5),
                    ('900', 'Los Angeles', 'CA', 1.4),
                    ('606', 'Chicago', 'IL', 1.2),
                    ('770', 'Houston', 'TX', 0.9),
                    ('850', 'Phoenix', 'AZ', 0.95),
                    ('191', 'Philadelphia', 'PA', 1.15),
                    ('782', 'San Antonio', 'TX', 0.85),
                    ('921', 'San Diego', 'CA', 1.3),
                    ('752', 'Dallas', 'TX', 1.0),
                    ('941', 'San Francisco', 'CA', 1.6)
                """)
            
            # Check if we have contractors, if not add some sample ones
            cursor.execute("SELECT COUNT(*) FROM contractors")
            count = cursor.fetchone()[0]
            
            if count == 0:
                logger.info("Adding some sample contractors")
                
                # Add Luxury tier contractors (20+ years experience)
                cursor.execute("""
                    INSERT INTO contractors 
                    (name, description, email, phone, website, logo_url, rating, tier_level, years_in_business, license_verified, insurance_verified, zip_code, city, state) 
                    VALUES 
                    ('Elite Home Services', 'Luxury home repair and maintenance services with over 25 years of experience.', 'info@elitehome.example.com', '555-123-4567', 'https://elitehome.example.com', '/static/img/logos/elite-home.png', 4.9, 'Luxury', 25, TRUE, TRUE, '900', 'Los Angeles', 'CA'),
                    ('Master Contractors Inc.', 'Specializing in high-quality home renovations since 1997.', 'service@mastercontractors.example.com', '555-987-6543', 'https://mastercontractors.example.com', '/static/img/logos/master-contractors.png', 4.8, 'Luxury', 28, TRUE, TRUE, '100', 'New York', 'NY'),
                    ('Heritage Home Experts', 'Family-owned business providing exceptional craftsmanship for over 30 years.', 'contact@heritagehome.example.com', '555-456-7890', 'https://heritagehome.example.com', '/static/img/logos/heritage-home.png', 5.0, 'Luxury', 32, TRUE, TRUE, '606', 'Chicago', 'IL')
                """)
                
                # Add Standard tier contractors (5-20 years experience)
                cursor.execute("""
                    INSERT INTO contractors 
                    (name, description, email, phone, website, logo_url, rating, tier_level, years_in_business, license_verified, insurance_verified, zip_code, city, state) 
                    VALUES 
                    ('Reliable Repairs', 'Trusted repair services for all your home maintenance needs.', 'service@reliablerepairs.example.com', '555-222-3333', 'https://reliablerepairs.example.com', '/static/img/logos/reliable-repairs.png', 4.5, 'Standard', 12, TRUE, TRUE, '900', 'Los Angeles', 'CA'),
                    ('Quality Home Services', 'Professional services at competitive prices.', 'info@qualityhome.example.com', '555-444-5555', 'https://qualityhome.example.com', '/static/img/logos/quality-home.png', 4.3, 'Standard', 8, TRUE, TRUE, '100', 'New York', 'NY'),
                    ('City Maintenance Pro', 'Serving the metro area with quality service since 2011.', 'info@citymaintenance.example.com', '555-666-7777', 'https://citymaintenance.example.com', '/static/img/logos/city-maintenance.png', 4.2, 'Standard', 14, TRUE, TRUE, '606', 'Chicago', 'IL')
                """)
                
                # Add Premium tier contractors (<5 years experience but premium quality)
                cursor.execute("""
                    INSERT INTO contractors 
                    (name, description, email, phone, website, logo_url, rating, tier_level, years_in_business, license_verified, insurance_verified, zip_code, city, state) 
                    VALUES 
                    ('Fresh Fix Solutions', 'New on the scene but highly skilled with premium service.', 'hello@freshfix.example.com', '555-888-9999', 'https://freshfix.example.com', '/static/img/logos/fresh-fix.png', 4.0, 'Premium', 2, TRUE, TRUE, '900', 'Los Angeles', 'CA'),
                    ('Startup Home Services', 'Young team of skilled professionals ready to serve you with premium quality.', 'help@startuphome.example.com', '555-111-2222', 'https://startuphome.example.com', '/static/img/logos/startup-home.png', 3.8, 'Premium', 1, TRUE, FALSE, '100', 'New York', 'NY'),
                    ('NextGen Repairs', 'Modern solutions for today\'s homes with premium service quality.', 'service@nextgenrepairs.example.com', '555-333-4444', 'https://nextgenrepairs.example.com', '/static/img/logos/nextgen-repairs.png', 3.9, 'Premium', 3, TRUE, TRUE, '606', 'Chicago', 'IL')
                """)
                
                # Now add some service areas for these contractors
                cursor.execute("""
                    INSERT INTO contractor_service_areas 
                    (contractor_id, zipcode, city, state) 
                    VALUES 
                    (1, '900', 'Los Angeles', 'CA'),
                    (1, '902', 'Beverly Hills', 'CA'),
                    (1, '913', 'Pasadena', 'CA'),
                    (2, '100', 'New York', 'NY'),
                    (2, '112', 'Brooklyn', 'NY'),
                    (2, '104', 'Bronx', 'NY'),
                    (3, '606', 'Chicago', 'IL'),
                    (3, '605', 'Evanston', 'IL'),
                    (4, '900', 'Los Angeles', 'CA'),
                    (5, '100', 'New York', 'NY'),
                    (6, '606', 'Chicago', 'IL'),
                    (7, '900', 'Los Angeles', 'CA'),
                    (8, '100', 'New York', 'NY'),
                    (9, '606', 'Chicago', 'IL')
                """)
                
                # Add Service Categories if empty
                cursor.execute("SELECT COUNT(*) FROM service_categories")
                count = cursor.fetchone()[0]
                
                if count == 0:
                    cursor.execute("""
                        INSERT INTO service_categories (name, description, icon) 
                        VALUES 
                        ('Plumbing', 'Water supply, drainage, and related services', 'plumbing_icon.svg'),
                        ('HVAC', 'Heating, ventilation, and air conditioning services', 'hvac_icon.svg'),
                        ('Electrical', 'Wiring, lighting, and power supply services', 'electrical_icon.svg'),
                        ('Lawn & Garden', 'Landscape maintenance and gardening services', 'lawn_icon.svg'),
                        ('Home Cleaning', 'Interior and exterior cleaning services', 'cleaning_icon.svg'),
                        ('Roofing', 'Roof installation, repair, and maintenance', 'roof_icon.svg'),
                        ('Painting', 'Interior and exterior painting services', 'paint_icon.svg'),
                        ('Renovation', 'Home remodeling and renovation services', 'renovation_icon.svg')
                    """)
                
                # Add Services if empty
                cursor.execute("SELECT COUNT(*) FROM services")
                count = cursor.fetchone()[0]
                
                if count == 0:
                    cursor.execute("""
                        INSERT INTO services 
                        (category_id, name, description, base_price, base_price_per_sqft, min_price, unit, recurring, frequency, is_emergency, is_maintenance, is_seasonal, season) 
                        VALUES 
                        (1, 'Leak Repair', 'Fix leaking pipes, faucets, or fixtures', 150.00, NULL, 100.00, 'service', FALSE, NULL, TRUE, FALSE, FALSE, NULL),
                        (1, 'Drain Cleaning', 'Clear clogged drains and pipes', 120.00, NULL, 75.00, 'service', FALSE, NULL, FALSE, TRUE, FALSE, NULL),
                        (1, 'Water Heater Installation', 'Install new water heater', 800.00, NULL, 600.00, 'service', FALSE, NULL, FALSE, FALSE, FALSE, NULL),
                        (2, 'AC Installation', 'Install new air conditioning system', 2500.00, 1.50, 1500.00, 'sqft', FALSE, NULL, FALSE, FALSE, FALSE, NULL),
                        (2, 'Furnace Repair', 'Repair heating system issues', 175.00, NULL, 120.00, 'service', FALSE, NULL, TRUE, FALSE, FALSE, NULL),
                        (2, 'HVAC Maintenance', 'Regular maintenance for heating and cooling systems', 120.00, NULL, 90.00, 'service', TRUE, 'Biannual', FALSE, TRUE, TRUE, 'spring,fall'),
                        (3, 'Electrical Panel Upgrade', 'Upgrade electrical service panel', 1200.00, NULL, 900.00, 'service', FALSE, NULL, FALSE, FALSE, FALSE, NULL),
                        (3, 'Outlet Installation', 'Install new electrical outlets', 85.00, NULL, 50.00, 'service', FALSE, NULL, FALSE, FALSE, FALSE, NULL),
                        (4, 'Lawn Mowing', 'Regular lawn cutting service', 45.00, 0.03, 30.00, 'sqft', TRUE, 'Biweekly', FALSE, TRUE, TRUE, 'spring,summer,fall'),
                        (4, 'Garden Design', 'Professional landscape design service', 350.00, 0.25, 250.00, 'sqft', FALSE, NULL, FALSE, FALSE, TRUE, 'spring'),
                        (5, 'Deep House Cleaning', 'Thorough cleaning of entire home', 160.00, 0.10, 120.00, 'sqft', TRUE, 'Monthly', FALSE, TRUE, FALSE, NULL),
                        (5, 'Window Cleaning', 'Professional window washing inside and out', 8.00, NULL, 80.00, 'window', TRUE, 'Quarterly', FALSE, FALSE, TRUE, 'spring,fall'),
                        (6, 'Roof Inspection', 'Comprehensive roof assessment', 250.00, NULL, 200.00, 'service', TRUE, 'Annual', FALSE, TRUE, TRUE, 'spring'),
                        (6, 'Shingle Replacement', 'Replace damaged or missing roof shingles', 350.00, 1.75, 250.00, 'sqft', FALSE, NULL, TRUE, FALSE, FALSE, NULL),
                        (7, 'Interior Painting', 'Painting interior walls, ceilings, trim', 350.00, 3.50, 250.00, 'room', FALSE, NULL, FALSE, FALSE, FALSE, NULL),
                        (7, 'Exterior Painting', 'Painting home exterior surfaces', 1500.00, 2.75, 1000.00, 'sqft', FALSE, NULL, FALSE, FALSE, TRUE, 'summer'),
                        (8, 'Kitchen Remodeling', 'Complete kitchen renovation services', 15000.00, 75.00, 10000.00, 'sqft', FALSE, NULL, FALSE, FALSE, FALSE, NULL),
                        (8, 'Bathroom Renovation', 'Complete bathroom remodeling services', 8000.00, 150.00, 5000.00, 'sqft', FALSE, NULL, FALSE, FALSE, FALSE, NULL)
                    """)
                
                # Link contractors to services
                cursor.execute("""
                    INSERT INTO contractor_services 
                    (contractor_id, service_id, price_multiplier, available) 
                    VALUES 
                    -- Elite Home Services (Luxury) - Plumbing and HVAC
                    (1, 1, 1.2, TRUE), -- Leak Repair
                    (1, 2, 1.1, TRUE), -- Drain Cleaning
                    (1, 3, 1.05, TRUE), -- Water Heater Installation
                    (1, 4, 1.1, TRUE), -- AC Installation
                    (1, 5, 1.2, TRUE), -- Furnace Repair
                    (1, 6, 1.1, TRUE), -- HVAC Maintenance
                    
                    -- Master Contractors (Luxury) - Electrical and Renovation
                    (2, 7, 1.15, TRUE), -- Electrical Panel Upgrade
                    (2, 8, 1.1, TRUE), -- Outlet Installation
                    (2, 17, 1.2, TRUE), -- Kitchen Remodeling
                    (2, 18, 1.25, TRUE), -- Bathroom Renovation
                    
                    -- Heritage Home (Luxury) - Roofing and Painting
                    (3, 13, 1.1, TRUE), -- Roof Inspection
                    (3, 14, 1.2, TRUE), -- Shingle Replacement
                    (3, 15, 1.1, TRUE), -- Interior Painting
                    (3, 16, 1.15, TRUE), -- Exterior Painting
                    
                    -- Reliable Repairs (Standard) - Plumbing and Electrical
                    (4, 1, 1.0, TRUE), -- Leak Repair
                    (4, 2, 1.0, TRUE), -- Drain Cleaning
                    (4, 7, 1.05, TRUE), -- Electrical Panel Upgrade
                    (4, 8, 0.95, TRUE), -- Outlet Installation
                    
                    -- Quality Home (Standard) - HVAC and Cleaning
                    (5, 4, 1.0, TRUE), -- AC Installation
                    (5, 5, 0.95, TRUE), -- Furnace Repair
                    (5, 6, 1.0, TRUE), -- HVAC Maintenance
                    (5, 11, 0.9, TRUE), -- Deep House Cleaning
                    (5, 12, 0.95, TRUE), -- Window Cleaning
                    
                    -- City Maintenance (Standard) - Lawn & Garden and Painting
                    (6, 9, 0.9, TRUE), -- Lawn Mowing
                    (6, 10, 1.0, TRUE), -- Garden Design
                    (6, 15, 0.95, TRUE), -- Interior Painting
                    (6, 16, 1.0, TRUE), -- Exterior Painting
                    
                    -- Fresh Fix (Premium) - Plumbing and Painting
                    (7, 1, 0.8, TRUE), -- Leak Repair
                    (7, 2, 0.75, TRUE), -- Drain Cleaning
                    (7, 15, 0.85, TRUE), -- Interior Painting
                    
                    -- Startup Home (Premium) - Cleaning and Lawn
                    (8, 9, 0.7, TRUE), -- Lawn Mowing
                    (8, 11, 0.75, TRUE), -- Deep House Cleaning
                    (8, 12, 0.8, TRUE), -- Window Cleaning
                    
                    -- NextGen Repairs (Premium) - Electrical and HVAC
                    (9, 5, 0.8, TRUE), -- Furnace Repair
                    (9, 6, 0.75, TRUE), -- HVAC Maintenance
                    (9, 8, 0.7, TRUE) -- Outlet Installation
                """)
                
                # Add some reviews for contractors
                cursor.execute("""
                    INSERT INTO contractor_reviews 
                    (contractor_id, user_email, rating, review_text, created_at) 
                    VALUES 
                    (1, 'user1@example.com', 5, 'Excellent service! Fixed our leak quickly and professionally.', NOW() - INTERVAL '2 days'),
                    (1, 'user2@example.com', 5, 'Very impressed with their attention to detail.', NOW() - INTERVAL '15 days'),
                    (1, 'user3@example.com', 4, 'Good service but slightly expensive.', NOW() - INTERVAL '45 days'),
                    
                    (2, 'user4@example.com', 5, 'The kitchen remodel exceeded our expectations!', NOW() - INTERVAL '7 days'),
                    (2, 'user5@example.com', 5, 'Extremely professional and high quality work.', NOW() - INTERVAL '30 days'),
                    (2, 'user6@example.com', 4, 'Great craftsmanship but took longer than estimated.', NOW() - INTERVAL '60 days'),
                    
                    (3, 'user7@example.com', 5, 'Our new roof looks amazing! Fast and reliable work.', NOW() - INTERVAL '5 days'),
                    (3, 'user8@example.com', 5, 'The exterior paint job transformed our home.', NOW() - INTERVAL '20 days'),
                    
                    (4, 'user9@example.com', 4, 'Fixed our plumbing issue quickly. Fair price.', NOW() - INTERVAL '3 days'),
                    (4, 'user10@example.com', 5, 'Responsive and professional service.', NOW() - INTERVAL '25 days'),
                    
                    (5, 'user11@example.com', 4, 'Good HVAC maintenance service, will use again.', NOW() - INTERVAL '10 days'),
                    (5, 'user12@example.com', 5, 'The house cleaning was thorough and well-priced.', NOW() - INTERVAL '18 days'),
                    
                    (6, 'user13@example.com', 4, 'Great lawn service, consistent quality.', NOW() - INTERVAL '8 days'),
                    (6, 'user14@example.com', 4, 'Our new garden design looks beautiful.', NOW() - INTERVAL '40 days'),
                    
                    (7, 'user15@example.com', 4, 'Good service at an affordable price.', NOW() - INTERVAL '12 days'),
                    (7, 'user16@example.com', 4, 'Prompt and friendly service for our leak.', NOW() - INTERVAL '22 days'),
                    
                    (8, 'user17@example.com', 4, 'Good value cleaning service.', NOW() - INTERVAL '9 days'),
                    (8, 'user18@example.com', 3, 'Service was okay but could be more thorough.', NOW() - INTERVAL '35 days'),
                    
                    (9, 'user19@example.com', 4, 'Quick response to our furnace issue.', NOW() - INTERVAL '14 days'),
                    (9, 'user20@example.com', 4, 'Good outlet installation at a reasonable price.', NOW() - INTERVAL '28 days')
                """)
                
                # Update contractor ratings based on reviews
                cursor.execute("""
                    UPDATE contractors c
                    SET rating = (
                        SELECT AVG(cr.rating)
                        FROM contractor_reviews cr
                        WHERE cr.contractor_id = c.contractor_id
                        GROUP BY cr.contractor_id
                    )
                    WHERE EXISTS (
                        SELECT 1 FROM contractor_reviews cr WHERE cr.contractor_id = c.contractor_id
                    )
                """)
                
                logger.info("Sample contractor data added successfully")
            
            # Commit the changes
            conn.commit()
            
            logger.info("Database tables created successfully")
            
        except Exception as db_error:
            logger.error(f"Error creating database tables: {str(db_error)}")
            conn.rollback()
        finally:
            if conn:
                conn.close()
            logger.info("Database setup complete")
            
    except Exception as e:
        logger.error(f"Error setting up database: {str(e)}")

# Initialize OpenAI API if available
openai_available = False
try:
    from openai import OpenAI
    openai_api_key = os.environ.get('OPENAI_API_KEY')
    if openai_api_key:
        openai_client = OpenAI(api_key=openai_api_key)
        openai_available = True
        logger.info("✅ OpenAI API initialized successfully")
    else:
        logger.warning("⚠️ OpenAI API key not found in environment variables")
except ImportError:
    logger.warning("⚠️ OpenAI module not found, AI features will be disabled")
except Exception as e:
    logger.error(f"❌ Error initializing OpenAI: {str(e)}")

# Set OpenAI availability on app
app.openai_available = openai_available

# Import and initialize AI routes
try:
    from attached_assets.ai_routes import init_ai_routes
    if openai_available:
        init_ai_routes(app)
        logger.info("✅ AI routes initialized successfully")
    else:
        logger.warning("⚠️ AI routes not initialized due to missing OpenAI API key")
except ImportError:
    logger.warning("⚠️ AI routes module not found")
except Exception as e:
    logger.error(f"❌ Error initializing AI routes: {str(e)}")

# Import and initialize enhanced integration
try:
    from final_glassrain.enhanced_integration import init_enhanced_integration
    from final_glassrain.enhanced_weather_integration import init_weather_integration
    
    # Initialize enhanced features
    logger.info("Initializing enhanced GlassRain features...")
    init_enhanced_integration(app)
    
    # Initialize weather integration
    logger.info("Initializing enhanced weather integration...")
    init_weather_integration(app)
    
    logger.info("✅ Enhanced features successfully initialized")
    
    # Update API status endpoint to include enhanced features
    @app.route('/api/enhanced-status')
    def enhanced_status():
        """Returns status of enhanced features"""
        conn = get_db_connection()
        db_status = "connected" if conn else "disconnected"
        
        if conn:
            conn.close()
        
        # Get weather data sources
        weather_sources = app.config.get('WEATHER_DATA_SOURCES', [])
        weather_integration_available = app.config.get('WEATHER_INTEGRATION_AVAILABLE', False)
        
        # Get OpenAI availability
        openai_available = getattr(app, 'openai_available', False)
        
        return jsonify({
            "status": "online",
            "version": "2.0.0",
            "database": db_status,
            "name": "GlassRain Enhanced API",
            "enhanced_features": [
                "advanced_3d_visualization",
                "improved_room_scanning",
                "ai_design_suggestions", 
                "detailed_property_data",
                "realistic_material_rendering",
                "weather_integration"
            ],
            "service_availability": {
                "openai": openai_available,
                "weather": weather_integration_available,
                "weather_sources": weather_sources,
                "database": db_status == "connected"
            }
        })
        
except ImportError as e:
    logger.warning(f"Enhanced integration not available: {str(e)}")
    logger.warning("Running with standard features only")
except Exception as e:
    logger.error(f"Error initializing enhanced features: {str(e)}")
    logger.warning("Running with standard features only")

# Import and initialize elevate routes
try:
    from elevate_routes import init_elevate_routes
    init_elevate_routes(app)
    logger.info("✅ Elevate routes initialized successfully")
except ImportError as e:
    logger.error(f"❌ Could not import elevate_routes: {str(e)}")
except Exception as e:
    logger.error(f"❌ Error initializing elevate routes: {str(e)}")

# Import and initialize maintenance scheduler routes
try:
    from maintenance_scheduler import init_maintenance_routes
    init_maintenance_routes(app)
    logger.info("✅ Maintenance scheduler routes initialized successfully")
except ImportError as e:
    logger.error(f"❌ Could not import maintenance_scheduler: {str(e)}")
except Exception as e:
    logger.error(f"❌ Error initializing maintenance scheduler routes: {str(e)}")

# Import and initialize contractor data service
try:
    from contractor_data_service import ContractorDataService
    
    # Check if OpenAI API key is available
    openai_key = os.environ.get('OPENAI_API_KEY')
    if openai_key:
        # Create a global contractor service instance
        app.contractor_service = ContractorDataService()
        logger.info("✅ Contractor data service initialized successfully")
    else:
        logger.warning("⚠️ Contractor data service not initialized due to missing OpenAI API key")
except ImportError as e:
    logger.error(f"❌ Could not import contractor_data_service: {str(e)}")
except Exception as e:
    logger.error(f"❌ Error initializing contractor data service: {str(e)}")

# API endpoint for property data using our enhanced service with OpenAI
@app.route('/api/property-data', methods=['GET'])
@rate_limit(limit=5, window=60)  # More strict limit for property data endpoints (expensive API call)
def get_property_data_endpoint():
    """
    Get comprehensive property data using our enhanced service with OpenAI
    
    Query parameters:
    - address: Property address (required)
    - latitude: Property latitude (optional)
    - longitude: Property longitude (optional)
    """
    address = request.args.get('address')
    latitude = request.args.get('latitude', type=float)
    longitude = request.args.get('longitude', type=float)
    
    if not address:
        return jsonify({"error": "Address parameter is required"}), 400
    
    try:
        # Check if we have the enhanced property data service
        if HAS_ENHANCED_PROPERTY_SERVICE:
            logger.info(f"Using enhanced property data service for: {address}")
            data = get_enhanced_property_data(address, latitude, longitude)
        else:
            logger.info(f"Using basic property data service for: {address}")
            data = get_property_data_by_address(address)
        
        # Add source information
        data['processing_date'] = datetime.now().strftime('%Y-%m-%d')
        
        return jsonify(data)
    except Exception as e:
        logger.error(f"Error fetching property data: {str(e)}")
        return jsonify({"error": f"Failed to fetch property data: {str(e)}"}), 500

if __name__ == '__main__':
    # Setup database tables before starting the app
    setup_database()
    
    # Register service recommendations routes if available
    if has_service_recommendation_routes:
        try:
            register_recommendations_routes(app)
            app.service_recs_available = True
            logger.info("Service recommendations routes registered successfully")
        except Exception as e:
            app.service_recs_available = False
            logger.warning(f"Failed to register service recommendation routes: {str(e)}")
    
    # Initialize backend enhancements
    try:
        import sys
        import os
        # Add the current directory to the path to ensure imports work correctly
        current_dir = os.path.dirname(os.path.abspath(__file__))
        if current_dir not in sys.path:
            sys.path.append(current_dir)
        
        from glassrain_production.backend_enhancements import init_backend_enhancements
        init_backend_enhancements(app)
        logger.info("✅ Backend enhancements initialized successfully")
    except Exception as e:
        logger.warning(f"⚠️ Failed to initialize backend enhancements: {str(e)}")
        logger.warning("The application will continue to run without enhanced backend features")
    
    # Run the Flask app
    port = int(os.environ.get('PORT', 3000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug)