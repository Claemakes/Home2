"""
Service Recommendations Module for GlassRain

This module handles recommendations for seasonal and recurring services
based on property data, service history, and seasonal patterns.
"""

import logging
import datetime
import os
import psycopg2
from dateutil.relativedelta import relativedelta
from psycopg2.extras import RealDictCursor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_db_connection():
    """Get a connection to the PostgreSQL database using environment variables"""
    conn = None
    try:
        # Get DATABASE_URL from environment (preferred method for production)
        database_url = os.environ.get('DATABASE_URL')
        if database_url:
            # Render often provides postgres:// instead of postgresql://
            database_url = database_url.replace("postgres://", "postgresql://")
            conn = psycopg2.connect(database_url, connect_timeout=10)
        else:
            # Alternative: connect using individual environment variables
            dbname = os.environ.get('PGDATABASE', 'postgres')
            user = os.environ.get('PGUSER', 'postgres')
            password = os.environ.get('PGPASSWORD', '')
            host = os.environ.get('PGHOST', 'localhost')
            port = os.environ.get('PGPORT', '5432')
            conn = psycopg2.connect(
                dbname=dbname,
                user=user,
                password=password,
                host=host,
                port=port,
                connect_timeout=10
            )
        # Set autocommit - this is important for our service transactions
        conn.autocommit = True
        return conn
    except Exception as e:
        logger.error(f"Database connection error: {str(e)}")
        return None

# Define seasons with their respective months
SEASONS = {
    'winter': [12, 1, 2],
    'spring': [3, 4, 5],
    'summer': [6, 7, 8],
    'fall': [9, 10, 11]
}

# Define recurring frequency periods
FREQUENCY_PERIODS = {
    'Weekly': relativedelta(weeks=1),
    'Biweekly': relativedelta(weeks=2),
    'Monthly': relativedelta(months=1),
    'Quarterly': relativedelta(months=3),
    'Biannual': relativedelta(months=6),
    'Annual': relativedelta(years=1)
}

def get_current_season():
    """Determine the current season based on the month"""
    current_month = datetime.datetime.now().month
    
    for season, months in SEASONS.items():
        if current_month in months:
            return season
    
    return None  # Fallback, shouldn't happen

def get_upcoming_season():
    """Determine the upcoming season"""
    current_month = datetime.datetime.now().month
    next_month = current_month + 1 if current_month < 12 else 1
    
    for season, months in SEASONS.items():
        if next_month in months and current_month not in months:
            return season
    
    # If we're in the middle of a season, return the next season
    current_season = get_current_season()
    if current_season:
        seasons = list(SEASONS.keys())
        try:
            current_index = seasons.index(current_season)
            next_index = (current_index + 1) % len(seasons)
            return seasons[next_index]
        except ValueError:
            # If current_season not found in the list (shouldn't happen)
            return "spring"  # Default to spring as fallback
    else:
        return "spring"  # Default to spring as fallback

def get_service_recommendations(address_id=None, user_id=None, limit=3):
    """
    Get personalized service recommendations based on:
    1. Seasonal services appropriate for current/upcoming season
    2. Recurring services due for renewal
    3. Previously completed services that might need follow-up
    
    Args:
        address_id: ID of the property address
        user_id: ID of the user
        limit: Maximum number of recommendations to return
        
    Returns:
        List of service recommendation dictionaries
    """
    recommendations = []
    conn = get_db_connection()
    
    if not conn:
        logger.error("Failed to connect to database for service recommendations")
        return recommendations
    
    cursor = None
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        current_season = get_current_season()
        upcoming_season = get_upcoming_season()
        current_date = datetime.datetime.now().date()
        
        # 1. Find seasonal services appropriate for the current or upcoming season
        seasonal_query = """
            SELECT s.service_id, s.name, s.description, sc.name as category_name, s.season,
                   c.name as contractor_name, c.rating as contractor_rating, c.tier_level
            FROM services s
            JOIN service_categories sc ON s.category_id = sc.category_id
            LEFT JOIN contractor_services cs ON s.service_id = cs.service_id
            LEFT JOIN contractors c ON cs.contractor_id = c.contractor_id
            WHERE s.is_seasonal = TRUE 
              AND s.season LIKE %s
            ORDER BY c.rating DESC
            LIMIT %s
        """
        # Look for both current and upcoming season services
        seasonal_param = f"%{current_season}%" if current_season else "%"
        cursor.execute(seasonal_query, (seasonal_param, limit))
        seasonal_services = cursor.fetchall()
        
        for service in seasonal_services:
            # Check if season is None before using it in 'in' operator
            season = service['season'] or ''
            recommendations.append({
                'type': 'seasonal',
                'service_id': service['service_id'],
                'title': f"Seasonal {service['name']}",
                'description': service['description'],
                'category': service['category_name'],
                'contractor': service['contractor_name'] if service['contractor_name'] else "Available contractors",
                'priority': 'high' if current_season and current_season in season else 'medium',
                'seasonal': True,
                'season': current_season,
                'action': 'schedule',
                'icon': 'calendar-season'
            })
        
        # 2. Find recurring services due for renewal based on completed quotes
        if user_id:
            recurring_query = """
                SELECT s.service_id, s.name, s.description, s.frequency, q.created_at, 
                       sc.name as category_name, c.name as contractor_name
                FROM quotes q
                JOIN services s ON q.service_id = s.service_id
                JOIN service_categories sc ON s.category_id = sc.category_id
                LEFT JOIN contractors c ON q.contractor_id = c.contractor_id
                WHERE q.user_id = %s
                  AND q.status = 'completed'
                  AND s.recurring = TRUE
                ORDER BY q.created_at DESC
            """
            cursor.execute(recurring_query, (user_id,))
            recurring_services = cursor.fetchall()
            
            for service in recurring_services:
                frequency = service['frequency']
                last_service_date = service['created_at'].date() if service['created_at'] else None
                
                if frequency in FREQUENCY_PERIODS and last_service_date:
                    # Calculate next due date based on frequency
                    next_due_date = last_service_date + FREQUENCY_PERIODS[frequency]
                    days_until_due = (next_due_date - current_date).days
                    
                    # Only include if due within 30 days or overdue
                    if days_until_due <= 30:
                        status = "Overdue" if days_until_due < 0 else "Due Soon"
                        priority = "high" if days_until_due < 0 else "medium"
                        
                        recommendations.append({
                            'type': 'recurring',
                            'service_id': service['service_id'],
                            'title': f"{service['name']} ({status})",
                            'description': f"Last serviced on {last_service_date.strftime('%b %d, %Y')}. {service['frequency']} service.",
                            'category': service['category_name'],
                            'contractor': service['contractor_name'] if service['contractor_name'] else "Previous contractor",
                            'priority': priority,
                            'recurring': True,
                            'frequency': frequency,
                            'days_until_due': days_until_due,
                            'action': 'schedule',
                            'icon': 'repeat'
                        })
        
        # 3. Property-specific recommendations if address_id is provided
        if address_id:
            # Get property details to make specific recommendations
            property_query = """
                SELECT pd.*, a.city, a.state, a.zip
                FROM property_details pd
                JOIN addresses a ON pd.address_id = a.address_id
                WHERE pd.address_id = %s
            """
            cursor.execute(property_query, (address_id,))
            property_data = cursor.fetchone()
            
            if property_data:
                # Year-based recommendations (older homes need more maintenance)
                year_built = property_data.get('year_built')
                if year_built:
                    property_age = datetime.datetime.now().year - year_built
                    
                    # For older homes (30+ years), recommend inspections
                    if property_age > 30 and len(recommendations) < limit:
                        recommendations.append({
                            'type': 'property',
                            'title': "Home Systems Inspection",
                            'description': f"Your home is {property_age} years old. Consider a comprehensive inspection of major systems.",
                            'category': "Home Maintenance",
                            'priority': 'medium',
                            'property_age': property_age,
                            'action': 'learn_more',
                            'icon': 'home-inspect'
                        })
                    
                    # For homes built before 1980, recommend specific inspections
                    if year_built < 1980 and len(recommendations) < limit:
                        recommendations.append({
                            'type': 'property',
                            'title': "Safety Inspection",
                            'description': f"Older homes may have outdated electrical systems or hazardous materials.",
                            'category': "Safety",
                            'priority': 'high',
                            'property_age': property_age,
                            'action': 'safety_check',
                            'icon': 'safety'
                        })
                
                # Recommendations based on property features
                has_pool = property_data.get('has_pool', False)
                roof_type = property_data.get('roof_type')
                exterior_material = property_data.get('exterior_material')
                
                if has_pool and current_season == 'spring' and len(recommendations) < limit:
                    recommendations.append({
                        'type': 'property',
                        'title': "Pool Opening Service",
                        'description': "Time to prepare your pool for the summer season.",
                        'category': "Pool Maintenance",
                        'priority': 'medium',
                        'seasonal': True,
                        'season': 'spring',
                        'action': 'schedule',
                        'icon': 'pool'
                    })
                
                if roof_type and current_season in ['fall', 'winter'] and len(recommendations) < limit:
                    recommendations.append({
                        'type': 'property',
                        'title': "Roof Maintenance",
                        'description': f"Inspect your {roof_type} roof before winter weather arrives.",
                        'category': "Roofing",
                        'priority': 'high' if current_season == 'fall' else 'medium',
                        'seasonal': True,
                        'season': current_season,
                        'action': 'schedule',
                        'icon': 'roof'
                    })
        
        # Limit to requested number of recommendations
        recommendations = recommendations[:limit]
        
    except Exception as e:
        logger.error(f"Error getting service recommendations: {str(e)}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
    
    return recommendations

def get_upcoming_service_reminders(user_id, days_ahead=30):
    """
    Get reminders for upcoming services that should be scheduled
    based on seasonal timing and recurring schedule
    
    Args:
        user_id: ID of the user
        days_ahead: Number of days to look ahead for upcoming services
        
    Returns:
        List of service reminder dictionaries
    """
    reminders = []
    conn = get_db_connection()
    
    if not conn:
        logger.error("Failed to connect to database for service reminders")
        return reminders
    
    cursor = None
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        current_date = datetime.datetime.now().date()
        reminder_end_date = current_date + datetime.timedelta(days=days_ahead)
        
        # Get completed recurring services for this user
        query = """
            SELECT q.quote_id, q.created_at, q.address_id, 
                   s.service_id, s.name, s.description, s.frequency,
                   c.contractor_id, c.name as contractor_name
            FROM quotes q
            JOIN services s ON q.service_id = s.service_id
            LEFT JOIN contractors c ON q.contractor_id = c.contractor_id
            WHERE q.user_id = %s
              AND q.status = 'completed'
              AND s.recurring = TRUE
            ORDER BY q.created_at DESC
        """
        
        cursor.execute(query, (user_id,))
        services = cursor.fetchall()
        
        # Process each service to determine if it needs a reminder
        for service in services:
            frequency = service['frequency']
            last_service_date = service['created_at'].date() if service['created_at'] else None
            
            if frequency in FREQUENCY_PERIODS and last_service_date:
                # Calculate next due date based on frequency
                next_due_date = last_service_date + FREQUENCY_PERIODS[frequency]
                
                # Create reminder if due date is within reminder window
                if current_date <= next_due_date <= reminder_end_date:
                    days_until_due = (next_due_date - current_date).days
                    
                    reminders.append({
                        'service_id': service['service_id'],
                        'service_name': service['name'],
                        'description': service['description'],
                        'last_service_date': last_service_date.strftime('%b %d, %Y'),
                        'next_due_date': next_due_date.strftime('%b %d, %Y'),
                        'days_until_due': days_until_due,
                        'contractor_id': service['contractor_id'],
                        'contractor_name': service['contractor_name'],
                        'address_id': service['address_id'],
                        'frequency': frequency
                    })
        
    except Exception as e:
        logger.error(f"Error getting service reminders: {str(e)}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
    
    return reminders