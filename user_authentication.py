"""
User Authentication Module for GlassRain

Handles user authentication, registration, and session management.
"""

import os
import logging
import hashlib
import secrets
import time
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import session, request, flash, redirect, url_for

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class UserAuth:
    """User authentication handler"""
    
    def __init__(self):
        """Initialize authentication handler"""
        self.token_lifetime = 3600 * 24 * 7  # 1 week in seconds
        logger.info("User Authentication initialized")
        
    def _get_db_connection(self):
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
        
    def hash_password(self, password, salt=None):
        """
        Hash a password with a salt for secure storage
        
        Args:
            password (str): The plaintext password to hash
            salt (str, optional): A salt to use for hashing. If not provided, a new one is generated.
            
        Returns:
            tuple: (hashed_password, salt)
        """
        if not salt:
            salt = secrets.token_hex(16)
            
        # Hash the password with the salt
        hashed = hashlib.pbkdf2_hmac(
            'sha256', 
            password.encode('utf-8'), 
            salt.encode('utf-8'), 
            100000
        ).hex()
        
        return (hashed, salt)
        
    def verify_password(self, password, hashed_password, salt):
        """
        Verify a password against a hash
        
        Args:
            password (str): The plaintext password to verify
            hashed_password (str): The hashed password to check against
            salt (str): The salt used for hashing
            
        Returns:
            bool: True if the password matches, False otherwise
        """
        hashed, _ = self.hash_password(password, salt)
        return hashed == hashed_password
        
    def register(self, email, password, first_name=None, last_name=None):
        """
        Register a new user
        
        Args:
            email (str): User's email address
            password (str): User's password
            first_name (str, optional): User's first name
            last_name (str, optional): User's last name
            
        Returns:
            dict: Registration result with success flag and message or user data
        """
        try:
            # Validate email and password
            if not email or not password:
                return {
                    'success': False,
                    'message': 'Email and password are required'
                }
                
            if len(password) < 8:
                return {
                    'success': False,
                    'message': 'Password must be at least 8 characters long'
                }
                
            # Connect to database
            conn = self._get_db_connection()
            if not conn:
                return {
                    'success': False,
                    'message': 'Database connection failed'
                }
                
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Check if email already exists
            cursor.execute(
                "SELECT id FROM users WHERE email = %s",
                (email,)
            )
            
            if cursor.fetchone():
                cursor.close()
                conn.close()
                return {
                    'success': False,
                    'message': 'Email already registered'
                }
                
            # Hash the password
            hashed_password, salt = self.hash_password(password)
            
            # Store combined hash and salt separated by a colon
            password_hash = f"{hashed_password}:{salt}"
            
            # Insert the new user
            cursor.execute(
                """
                INSERT INTO users (email, password_hash, first_name, last_name)
                VALUES (%s, %s, %s, %s)
                RETURNING id, email, first_name, last_name, created_at
                """,
                (email, password_hash, first_name, last_name)
            )
            
            user = cursor.fetchone()
            
            cursor.close()
            conn.close()
            
            if user:
                # Set session data
                session['user_id'] = user['id']
                session['email'] = user['email']
                session['first_name'] = user['first_name']
                session['last_name'] = user['last_name']
                session['is_admin'] = False
                session['authenticated_at'] = int(time.time())
                
                return {
                    'success': True,
                    'user': user
                }
            else:
                return {
                    'success': False,
                    'message': 'Registration failed for unknown reason'
                }
                
        except Exception as e:
            logger.error(f"Registration error: {e}")
            return {
                'success': False,
                'message': f"Registration error: {str(e)}"
            }
            
    def login(self, email, password):
        """
        Log in a user
        
        Args:
            email (str): User's email address
            password (str): User's password
            
        Returns:
            dict: Login result with success flag and message or user data
        """
        try:
            # Validate email and password
            if not email or not password:
                return {
                    'success': False,
                    'message': 'Email and password are required'
                }
                
            # Connect to database
            conn = self._get_db_connection()
            if not conn:
                return {
                    'success': False,
                    'message': 'Database connection failed'
                }
                
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Get user by email
            cursor.execute(
                """
                SELECT id, email, password_hash, first_name, last_name, created_at
                FROM users WHERE email = %s
                """,
                (email,)
            )
            
            user = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if not user:
                return {
                    'success': False,
                    'message': 'Invalid email or password'
                }
                
            # Split the stored hash and salt
            try:
                hashed_password, salt = user['password_hash'].split(':')
            except ValueError:
                return {
                    'success': False,
                    'message': 'Invalid account data, please contact support'
                }
                
            # Verify the password
            if not self.verify_password(password, hashed_password, salt):
                return {
                    'success': False,
                    'message': 'Invalid email or password'
                }
                
            # Set session data
            session['user_id'] = user['id']
            session['email'] = user['email']
            session['first_name'] = user['first_name']
            session['last_name'] = user['last_name']
            session['is_admin'] = False  # Could be retrieved from the database
            session['authenticated_at'] = int(time.time())
            
            # Remove sensitive data from response
            del user['password_hash']
            
            return {
                'success': True,
                'user': user
            }
                
        except Exception as e:
            logger.error(f"Login error: {e}")
            return {
                'success': False,
                'message': f"Login error: {str(e)}"
            }
            
    def logout(self):
        """
        Log out the current user
        
        Returns:
            dict: Logout result with success flag
        """
        try:
            # Clear session data
            session.clear()
            return {
                'success': True,
                'message': 'Logged out successfully'
            }
        except Exception as e:
            logger.error(f"Logout error: {e}")
            return {
                'success': False,
                'message': f"Logout error: {str(e)}"
            }
            
    def is_authenticated(self):
        """
        Check if the user is authenticated
        
        Returns:
            bool: True if authenticated, False otherwise
        """
        if 'user_id' not in session:
            return False
            
        # Check authentication timestamp
        auth_time = session.get('authenticated_at', 0)
        current_time = int(time.time())
        
        if current_time - auth_time > self.token_lifetime:
            # Session has expired
            session.clear()
            return False
            
        return True
        
    def get_current_user(self):
        """
        Get the current user's data
        
        Returns:
            dict: User data or None if not authenticated
        """
        if not self.is_authenticated():
            return None
            
        # Connect to database
        conn = self._get_db_connection()
        if not conn:
            logger.error("Database connection failed in get_current_user")
            return None
            
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Get user by ID
            cursor.execute(
                """
                SELECT id, email, first_name, last_name, created_at
                FROM users WHERE id = %s
                """,
                (session['user_id'],)
            )
            
            user = cursor.fetchone()
            cursor.close()
            conn.close()
            
            return user
        except Exception as e:
            logger.error(f"Error getting current user: {e}")
            return None