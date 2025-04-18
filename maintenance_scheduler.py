"""
Maintenance Scheduler Service

This module manages the creation, tracking, and notification of maintenance schedules
based on service quotes. It handles recurring services like seasonal maintenance as well
as one-time service appointments.

Key features:
- Create maintenance schedules from service quotes
- Determine optimal scheduling based on service type and user preferences
- Generate reminders for upcoming maintenance
- Track maintenance history
- Support recurring services with different frequencies (seasonal, monthly, weekly)
"""

import os
import json
import logging
import datetime
from typing import Dict, List, Optional, Any, Union
from dateutil.relativedelta import relativedelta
import psycopg2
from psycopg2.extras import RealDictCursor

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('maintenance_scheduler')

class MaintenanceScheduler:
    """Service for scheduling and tracking property maintenance"""
    
    # Service frequency mappings to time periods
    FREQUENCY_MAPPING = {
        'weekly': {'weeks': 1},
        'bi-weekly': {'weeks': 2},
        'monthly': {'months': 1},
        'quarterly': {'months': 3},
        'semi-annual': {'months': 6},
        'annual': {'years': 1},
        'spring': {'month': 3, 'day': 15},  # March 15th
        'summer': {'month': 6, 'day': 15},  # June 15th
        'fall': {'month': 9, 'day': 15},    # September 15th
        'winter': {'month': 12, 'day': 15}, # December 15th
    }
    
    def __init__(self, db_connection=None):
        """Initialize with database connection"""
        self.conn = db_connection
    
    def get_db_connection(self):
        """Get a database connection if one doesn't exist"""
        if self.conn and not self.conn.closed:
            return self.conn
            
        # Use environment variables for connection
        try:
            conn = psycopg2.connect(
                dbname=os.environ.get('PGDATABASE', 'postgres'),
                user=os.environ.get('PGUSER', 'postgres'),
                password=os.environ.get('PGPASSWORD', ''),
                host=os.environ.get('PGHOST', 'localhost'),
                port=os.environ.get('PGPORT', '5432')
            )
            self.conn = conn
            return conn
        except Exception as e:
            logger.error(f"Database connection error: {str(e)}")
            return None
    
    def create_maintenance_schedule(self, quote_id: int) -> Dict[str, Any]:
        """
        Create a maintenance schedule based on a service quote
        
        Args:
            quote_id: ID of the service quote
            
        Returns:
            Dictionary containing schedule information
        """
        conn = self.get_db_connection()
        if not conn:
            logger.error("Database connection failed")
            return {"error": "Database connection failed"}
        
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Get the quote details
            cursor.execute("""
                SELECT q.*, s.name as service_name, s.description as service_description, 
                       s.category_id, s.recurring, s.frequency, s.is_seasonal, s.season,
                       c.name as contractor_name, c.contact_email, c.phone
                FROM quotes q
                JOIN services s ON q.service_id = s.service_id
                JOIN contractors c ON q.contractor_id = c.contractor_id
                WHERE q.quote_id = %s
            """, [quote_id])
            
            quote = cursor.fetchone()
            if not quote:
                logger.error(f"Quote not found: {quote_id}")
                return {"error": "Quote not found"}
            
            # Get the user details
            cursor.execute("""
                SELECT * FROM users WHERE user_id = %s
            """, [quote.get('user_id')])
            
            user = cursor.fetchone()
            # If user not found, create basic user record from the quote
            if not user:
                logger.warning(f"User not found for quote {quote_id}, creating placeholder record")
                user = {"user_id": quote.get('user_id'), "email": quote.get('user_id')}
            
            # Determine scheduling based on service type
            is_recurring = quote.get('recurring', False)
            service_frequency = quote.get('frequency', 'one-time').lower()
            is_seasonal = quote.get('is_seasonal', False)
            season = quote.get('season', 'spring').lower()
            
            # Get the requested date from the quote
            requested_date = quote.get('requested_date')
            if not requested_date:
                requested_date = datetime.datetime.now().strftime('%Y-%m-%d')
            
            # Calculate initial appointment date
            initial_date = self._calculate_initial_appointment(
                requested_date, is_recurring, service_frequency, is_seasonal, season
            )
            
            # Generate future dates for recurring services
            future_dates = []
            if is_recurring:
                future_dates = self._generate_recurring_dates(
                    initial_date, service_frequency, 5  # Generate next 5 occurrences
                )
            
            # Create the schedule record
            schedule_data = {
                'quote_id': quote_id,
                'user_id': quote.get('user_id'),
                'service_id': quote.get('service_id'),
                'contractor_id': quote.get('contractor_id'),
                'is_recurring': is_recurring,
                'frequency': service_frequency,
                'is_seasonal': is_seasonal,
                'season': season,
                'initial_date': initial_date,
                'next_date': initial_date,
                'future_dates': future_dates,
                'status': 'scheduled',
                'reminders_sent': 0,
                'last_completed': None
            }
            
            # Store in database
            columns = ", ".join(schedule_data.keys())
            placeholders = ", ".join(["%s"] * len(schedule_data))
            values = list(schedule_data.values())
            
            cursor.execute(f"""
                INSERT INTO maintenance_schedules (
                    {columns}, created_at
                ) VALUES (
                    {placeholders}, NOW()
                ) RETURNING schedule_id
            """, values)
            
            schedule_id = cursor.fetchone()['schedule_id']
            schedule_data['schedule_id'] = schedule_id
            
            # Update the quote with the schedule_id
            cursor.execute("""
                UPDATE quotes SET maintenance_schedule_id = %s WHERE quote_id = %s
            """, [schedule_id, quote_id])
            
            conn.commit()
            cursor.close()
            
            return {
                "success": True,
                "schedule_id": schedule_id,
                "message": "Maintenance schedule created successfully",
                "schedule": schedule_data
            }
            
        except Exception as e:
            logger.error(f"Error creating maintenance schedule: {str(e)}")
            if conn:
                conn.rollback()
            return {"error": f"Failed to create maintenance schedule: {str(e)}"}
            
        finally:
            if conn and conn != self.conn:
                conn.close()
    
    def _calculate_initial_appointment(
        self, 
        requested_date: str, 
        is_recurring: bool, 
        frequency: str, 
        is_seasonal: bool, 
        season: str
    ) -> str:
        """
        Calculate the optimal initial appointment date
        
        Args:
            requested_date: User's requested date
            is_recurring: Whether the service is recurring
            frequency: Service frequency (weekly, monthly, etc.)
            is_seasonal: Whether the service is seasonal
            season: Season for seasonal services
            
        Returns:
            Initial appointment date as string (YYYY-MM-DD)
        """
        try:
            # Parse the requested date
            if isinstance(requested_date, str):
                requested_date = datetime.datetime.strptime(requested_date, '%Y-%m-%d')
            
            # For one-time services, use the requested date
            if not is_recurring and not is_seasonal:
                return requested_date.strftime('%Y-%m-%d')
            
            # For seasonal services, calculate based on the season
            if is_seasonal:
                current_year = datetime.datetime.now().year
                if season in self.FREQUENCY_MAPPING:
                    month = self.FREQUENCY_MAPPING[season]['month']
                    day = self.FREQUENCY_MAPPING[season]['day']
                    seasonal_date = datetime.datetime(current_year, month, day)
                    
                    # If the seasonal date has already passed this year, use next year
                    if seasonal_date < datetime.datetime.now():
                        seasonal_date = datetime.datetime(current_year + 1, month, day)
                    
                    return seasonal_date.strftime('%Y-%m-%d')
            
            # For other recurring services, start with the requested date
            # unless it's too soon (within 7 days)
            now = datetime.datetime.now()
            if (requested_date - now).days < 7:
                # Add the frequency offset to get a reasonable first appointment
                frequency_lower = frequency.lower()
                if frequency_lower in self.FREQUENCY_MAPPING:
                    time_offset = self.FREQUENCY_MAPPING[frequency_lower]
                    requested_date = now + relativedelta(**time_offset)
            
            return requested_date.strftime('%Y-%m-%d')
            
        except Exception as e:
            logger.error(f"Error calculating initial appointment: {str(e)}")
            # Default to 14 days from now
            return (datetime.datetime.now() + datetime.timedelta(days=14)).strftime('%Y-%m-%d')
    
    def _generate_recurring_dates(self, initial_date: str, frequency: str, count: int) -> List[str]:
        """
        Generate future recurring dates based on frequency
        
        Args:
            initial_date: Starting date
            frequency: Recurrence frequency
            count: Number of dates to generate
            
        Returns:
            List of future dates as strings (YYYY-MM-DD)
        """
        future_dates = []
        
        try:
            # Parse the initial date
            if isinstance(initial_date, str):
                current_date = datetime.datetime.strptime(initial_date, '%Y-%m-%d')
            else:
                current_date = initial_date
            
            # Generate dates based on frequency
            frequency_lower = frequency.lower()
            for i in range(count):
                if frequency_lower in self.FREQUENCY_MAPPING:
                    time_offset = self.FREQUENCY_MAPPING[frequency_lower]
                    
                    # Special handling for seasonal frequencies
                    if frequency_lower in ['spring', 'summer', 'fall', 'winter']:
                        # For seasonal, just add one year
                        current_date = datetime.datetime(
                            current_date.year + 1,
                            current_date.month,
                            current_date.day
                        )
                    else:
                        # For regular frequencies, add the appropriate interval
                        current_date = current_date + relativedelta(**time_offset)
                else:
                    # Default to monthly if frequency is not recognized
                    current_date = current_date + relativedelta(months=1)
                
                future_dates.append(current_date.strftime('%Y-%m-%d'))
                
            return future_dates
            
        except Exception as e:
            logger.error(f"Error generating recurring dates: {str(e)}")
            return []
    
    def get_upcoming_maintenance(self, user_id: str, days_ahead: int = 30) -> List[Dict[str, Any]]:
        """
        Get upcoming maintenance appointments for a user
        
        Args:
            user_id: User identifier
            days_ahead: Number of days to look ahead
            
        Returns:
            List of upcoming maintenance appointments
        """
        conn = self.get_db_connection()
        if not conn:
            logger.error("Database connection failed")
            return []
        
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Calculate cutoff date
            cutoff_date = (datetime.datetime.now() + datetime.timedelta(days=days_ahead)).strftime('%Y-%m-%d')
            
            # Get upcoming maintenance appointments
            cursor.execute("""
                SELECT 
                    ms.*, q.price as quote_price, q.status as quote_status,
                    s.name as service_name, s.description as service_description,
                    c.name as contractor_name, c.contact_email, c.phone
                FROM maintenance_schedules ms
                JOIN quotes q ON ms.quote_id = q.quote_id
                JOIN services s ON ms.service_id = s.service_id
                JOIN contractors c ON ms.contractor_id = c.contractor_id
                WHERE ms.user_id = %s AND ms.next_date <= %s AND ms.status = 'scheduled'
                ORDER BY ms.next_date ASC
            """, [user_id, cutoff_date])
            
            appointments = cursor.fetchall()
            cursor.close()
            
            return appointments
            
        except Exception as e:
            logger.error(f"Error getting upcoming maintenance: {str(e)}")
            return []
            
        finally:
            if conn and conn != self.conn:
                conn.close()
    
    def get_maintenance_history(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get maintenance history for a user
        
        Args:
            user_id: User identifier
            
        Returns:
            List of completed maintenance records
        """
        conn = self.get_db_connection()
        if not conn:
            logger.error("Database connection failed")
            return []
        
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Get completed maintenance records
            cursor.execute("""
                SELECT 
                    ms.*, q.price as quote_price, q.status as quote_status,
                    s.name as service_name, s.description as service_description,
                    c.name as contractor_name, c.contact_email, c.phone
                FROM maintenance_schedules ms
                JOIN quotes q ON ms.quote_id = q.quote_id
                JOIN services s ON ms.service_id = s.service_id
                JOIN contractors c ON ms.contractor_id = c.contractor_id
                WHERE ms.user_id = %s AND ms.last_completed IS NOT NULL
                ORDER BY ms.last_completed DESC
            """, [user_id])
            
            history = cursor.fetchall()
            cursor.close()
            
            return history
            
        except Exception as e:
            logger.error(f"Error getting maintenance history: {str(e)}")
            return []
            
        finally:
            if conn and conn != self.conn:
                conn.close()
    
    def update_next_maintenance_date(self, schedule_id: int) -> Dict[str, Any]:
        """
        Update the next maintenance date for a recurring schedule after completion
        
        Args:
            schedule_id: Maintenance schedule ID
            
        Returns:
            Dictionary with the updated schedule information
        """
        conn = self.get_db_connection()
        if not conn:
            logger.error("Database connection failed")
            return {"error": "Database connection failed"}
        
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Get the current schedule
            cursor.execute("SELECT * FROM maintenance_schedules WHERE schedule_id = %s", [schedule_id])
            schedule = cursor.fetchone()
            
            if not schedule:
                logger.error(f"Schedule not found: {schedule_id}")
                return {"error": "Schedule not found"}
            
            # Update the last_completed date
            now = datetime.datetime.now()
            cursor.execute("""
                UPDATE maintenance_schedules 
                SET last_completed = %s
                WHERE schedule_id = %s
            """, [now.strftime('%Y-%m-%d'), schedule_id])
            
            # If it's not recurring, mark as completed
            if not schedule.get('is_recurring'):
                cursor.execute("""
                    UPDATE maintenance_schedules 
                    SET status = 'completed', next_date = NULL
                    WHERE schedule_id = %s
                """, [schedule_id])
                
                conn.commit()
                
                return {
                    "success": True,
                    "message": "One-time maintenance marked as completed",
                    "status": "completed"
                }
            
            # For recurring maintenance, calculate the next date
            future_dates = schedule.get('future_dates', [])
            if future_dates and len(future_dates) > 0:
                # Pop the first future date
                next_date = future_dates[0]
                remaining_dates = future_dates[1:]
                
                # Generate a new future date to add to the end
                if len(remaining_dates) > 0:
                    last_date = remaining_dates[-1]
                    new_dates = self._generate_recurring_dates(
                        last_date, schedule.get('frequency', 'monthly'), 1
                    )
                    if new_dates:
                        remaining_dates.append(new_dates[0])
            else:
                # Calculate next date based on frequency
                frequency = schedule.get('frequency', 'monthly').lower()
                
                if frequency in self.FREQUENCY_MAPPING:
                    time_offset = self.FREQUENCY_MAPPING[frequency]
                    
                    # Special handling for seasonal frequencies
                    if frequency in ['spring', 'summer', 'fall', 'winter']:
                        # For seasonal, just add one year
                        month = self.FREQUENCY_MAPPING[frequency]['month']
                        day = self.FREQUENCY_MAPPING[frequency]['day']
                        next_date_obj = datetime.datetime(now.year + 1, month, day)
                    else:
                        # For regular frequencies, add the appropriate interval
                        next_date_obj = now + relativedelta(**time_offset)
                    
                    next_date = next_date_obj.strftime('%Y-%m-%d')
                    
                    # Also generate new future dates
                    remaining_dates = self._generate_recurring_dates(
                        next_date, frequency, 5
                    )
                else:
                    # Default to monthly if frequency not recognized
                    next_date_obj = now + relativedelta(months=1)
                    next_date = next_date_obj.strftime('%Y-%m-%d')
                    remaining_dates = []
            
            # Update the schedule
            cursor.execute("""
                UPDATE maintenance_schedules 
                SET next_date = %s, future_dates = %s, reminders_sent = 0
                WHERE schedule_id = %s
            """, [next_date, json.dumps(remaining_dates), schedule_id])
            
            conn.commit()
            
            return {
                "success": True,
                "message": "Maintenance completed and next date scheduled",
                "next_date": next_date,
                "future_dates": remaining_dates
            }
            
        except Exception as e:
            logger.error(f"Error updating next maintenance date: {str(e)}")
            if conn:
                conn.rollback()
            return {"error": f"Failed to update maintenance schedule: {str(e)}"}
            
        finally:
            if conn and conn != self.conn:
                conn.close()
    
    def send_maintenance_reminders(self, days_ahead: int = 7) -> Dict[str, Any]:
        """
        Send reminders for upcoming maintenance appointments
        
        Args:
            days_ahead: Number of days ahead to look for appointments
            
        Returns:
            Dictionary with statistics on reminders sent
        """
        conn = self.get_db_connection()
        if not conn:
            logger.error("Database connection failed")
            return {"error": "Database connection failed"}
        
        stats = {
            "reminders_sent": 0,
            "errors": 0
        }
        
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Calculate the reminder date range
            reminder_start = datetime.datetime.now().strftime('%Y-%m-%d')
            reminder_end = (datetime.datetime.now() + datetime.timedelta(days=days_ahead)).strftime('%Y-%m-%d')
            
            # Get schedules that need reminders
            cursor.execute("""
                SELECT 
                    ms.*, q.price as quote_price, q.status as quote_status,
                    s.name as service_name, s.description as service_description,
                    c.name as contractor_name, c.contact_email, c.phone,
                    u.email as user_email, u.name as user_name
                FROM maintenance_schedules ms
                JOIN quotes q ON ms.quote_id = q.quote_id
                JOIN services s ON ms.service_id = s.service_id
                JOIN contractors c ON ms.contractor_id = c.contractor_id
                JOIN users u ON ms.user_id = u.user_id
                WHERE ms.next_date BETWEEN %s AND %s 
                  AND ms.status = 'scheduled'
                  AND ms.reminders_sent = 0
            """, [reminder_start, reminder_end])
            
            schedules = cursor.fetchall()
            
            for schedule in schedules:
                try:
                    # In a real implementation, this would send an email
                    # For now, just log it
                    logger.info(f"Would send reminder to {schedule.get('user_email')} for {schedule.get('service_name')} on {schedule.get('next_date')}")
                    
                    # Update the reminder count
                    cursor.execute("""
                        UPDATE maintenance_schedules
                        SET reminders_sent = reminders_sent + 1
                        WHERE schedule_id = %s
                    """, [schedule.get('schedule_id')])
                    
                    stats["reminders_sent"] += 1
                    
                except Exception as reminder_error:
                    logger.error(f"Error sending reminder: {str(reminder_error)}")
                    stats["errors"] += 1
            
            conn.commit()
            cursor.close()
            
            return {
                "success": True,
                "message": f"Sent {stats['reminders_sent']} reminders with {stats['errors']} errors",
                "stats": stats
            }
            
        except Exception as e:
            logger.error(f"Error sending maintenance reminders: {str(e)}")
            if conn:
                conn.rollback()
            return {"error": f"Failed to send maintenance reminders: {str(e)}"}
            
        finally:
            if conn and conn != self.conn:
                conn.close()

# Initialize Flask blueprint for maintenance routes
from flask import Blueprint, request, jsonify

maintenance_bp = Blueprint('maintenance', __name__)

@maintenance_bp.route('/api/maintenance/schedule', methods=['POST'])
def create_schedule():
    """Create a maintenance schedule from a quote"""
    if not request.json or 'quote_id' not in request.json:
        return jsonify({"error": "quote_id is required"}), 400
    
    quote_id = request.json.get('quote_id')
    
    scheduler = MaintenanceScheduler()
    result = scheduler.create_maintenance_schedule(quote_id)
    
    if 'error' in result:
        return jsonify(result), 500
    
    return jsonify(result)

@maintenance_bp.route('/api/maintenance/upcoming/<user_id>', methods=['GET'])
def get_upcoming(user_id):
    """Get upcoming maintenance for a user"""
    days_ahead = request.args.get('days', 30, type=int)
    
    scheduler = MaintenanceScheduler()
    appointments = scheduler.get_upcoming_maintenance(user_id, days_ahead)
    
    return jsonify({"appointments": appointments})

@maintenance_bp.route('/api/maintenance/history/<user_id>', methods=['GET'])
def get_history(user_id):
    """Get maintenance history for a user"""
    scheduler = MaintenanceScheduler()
    history = scheduler.get_maintenance_history(user_id)
    
    return jsonify({"history": history})

@maintenance_bp.route('/api/maintenance/complete/<int:schedule_id>', methods=['POST'])
def complete_maintenance(schedule_id):
    """Mark maintenance as completed and schedule next appointment"""
    scheduler = MaintenanceScheduler()
    result = scheduler.update_next_maintenance_date(schedule_id)
    
    if 'error' in result:
        return jsonify(result), 500
    
    return jsonify(result)

def init_maintenance_routes(app):
    """Register maintenance routes with the Flask app"""
    app.register_blueprint(maintenance_bp)
    
    # Create tables if they don't exist
    setup_maintenance_tables()

def setup_maintenance_tables():
    """Create maintenance-related tables if they don't exist"""
    try:
        # Get database connection
        scheduler = MaintenanceScheduler()
        conn = scheduler.get_db_connection()
        
        if not conn:
            logger.error("Database connection failed, cannot create maintenance tables")
            return
        
        cursor = conn.cursor()
        
        # Create maintenance_schedules table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS maintenance_schedules (
                schedule_id SERIAL PRIMARY KEY,
                quote_id INTEGER REFERENCES quotes(quote_id),
                user_id VARCHAR(255),
                service_id INTEGER REFERENCES services(service_id),
                contractor_id INTEGER REFERENCES contractors(contractor_id),
                is_recurring BOOLEAN DEFAULT false,
                frequency VARCHAR(50),
                is_seasonal BOOLEAN DEFAULT false,
                season VARCHAR(20),
                initial_date DATE,
                next_date DATE,
                future_dates TEXT[] DEFAULT '{}',
                status VARCHAR(20) DEFAULT 'scheduled',
                reminders_sent INTEGER DEFAULT 0,
                last_completed DATE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        
        # Create index for faster lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_maintenance_user_id ON maintenance_schedules(user_id);
            CREATE INDEX IF NOT EXISTS idx_maintenance_next_date ON maintenance_schedules(next_date);
        """)
        
        # Add maintenance_schedule_id to quotes table if it doesn't exist
        cursor.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'quotes' AND column_name = 'maintenance_schedule_id'
                ) THEN
                    ALTER TABLE quotes ADD COLUMN maintenance_schedule_id INTEGER;
                END IF;
            END
            $$;
        """)
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info("Maintenance tables created successfully")
        
    except Exception as e:
        logger.error(f"Error creating maintenance tables: {str(e)}")
        if conn:
            conn.rollback()
            conn.close()

# For testing and direct module usage
if __name__ == "__main__":
    # Create tables
    setup_maintenance_tables()
    
    # Test the scheduler
    scheduler = MaintenanceScheduler()
    
    # Example of creating a schedule
    schedule_result = scheduler.create_maintenance_schedule(1)  # quote_id = 1
    print(json.dumps(schedule_result, indent=2))