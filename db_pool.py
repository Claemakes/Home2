"""
Database Connection Pool Module for GlassRain

This module provides a connection pool for PostgreSQL database connections,
improving performance by reusing connections instead of creating new ones
for each request.
"""

import os
import logging
import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import RealDictCursor

# Configure logging
logger = logging.getLogger(__name__)

# Global connection pool
_pool = None

def init_pool(min_conn=2, max_conn=10):
    """
    Initialize the connection pool.
    
    Args:
        min_conn: Minimum number of connections in the pool
        max_conn: Maximum number of connections in the pool
        
    Returns:
        bool: True if pool initialization was successful, False otherwise
    """
    global _pool
    
    # Don't initialize if already initialized
    if _pool is not None:
        return True
    
    try:
        # Get DATABASE_URL from environment (preferred method for production)
        database_url = os.environ.get('DATABASE_URL')
        
        if database_url:
            # Render often provides postgres:// instead of postgresql://
            database_url = database_url.replace("postgres://", "postgresql://")
            logger.info("Initializing connection pool with DATABASE_URL")
            _pool = ThreadedConnectionPool(min_conn, max_conn, database_url)
        else:
            # Alternative: connect using individual environment variables
            dbname = os.environ.get('PGDATABASE', 'postgres')
            user = os.environ.get('PGUSER', 'postgres')
            password = os.environ.get('PGPASSWORD', '')
            host = os.environ.get('PGHOST', 'localhost')
            port = os.environ.get('PGPORT', '5432')
            
            logger.info(f"Initializing connection pool for {dbname} at {host}:{port}")
            
            _pool = ThreadedConnectionPool(
                min_conn, max_conn,
                dbname=dbname,
                user=user,
                password=password,
                host=host,
                port=port,
                connect_timeout=10
            )
        
        # Test the pool with a simple query
        conn = _pool.getconn()
        try:
            with conn.cursor() as test_cursor:
                test_cursor.execute('SELECT 1')
                test_cursor.fetchone()
            logger.info("✅ Database connection pool initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to test database connection: {str(e)}")
            return False
        finally:
            _pool.putconn(conn)
            
    except Exception as e:
        logger.error(f"❌ Failed to initialize connection pool: {str(e)}")
        _pool = None
        return False

def get_connection():
    """
    Get a connection from the pool.
    
    Returns:
        Connection object or None if the pool is not initialized
    """
    global _pool
    
    if _pool is None:
        # Try to initialize the pool
        if not init_pool():
            logger.error("Database connection pool not initialized")
            return None
    
    try:
        conn = _pool.getconn()
        conn.autocommit = True  # Set autocommit mode
        return conn
    except Exception as e:
        logger.error(f"Error getting connection from pool: {str(e)}")
        return None

def return_connection(conn):
    """
    Return a connection to the pool.
    
    Args:
        conn: Connection object to return
    """
    global _pool
    
    if _pool is None or conn is None:
        return
    
    try:
        _pool.putconn(conn)
    except Exception as e:
        logger.error(f"Error returning connection to pool: {str(e)}")

def close_pool():
    """Close all connections in the pool and destroy the pool."""
    global _pool
    
    if _pool is not None:
        try:
            _pool.closeall()
            logger.info("Connection pool closed")
        except Exception as e:
            logger.error(f"Error closing connection pool: {str(e)}")
        finally:
            _pool = None

# Helper functions for common database operations
def execute_query(query, params=None, cursor_factory=RealDictCursor):
    """
    Execute a database query and return the results.
    
    Args:
        query: SQL query string
        params: Query parameters
        cursor_factory: Cursor factory to use
        
    Returns:
        Query results or None if an error occurred
    """
    conn = get_connection()
    if conn is None:
        return None
    
    cursor = None
    try:
        cursor = conn.cursor(cursor_factory=cursor_factory)
        cursor.execute(query, params or ())
        results = cursor.fetchall()
        return results
    except Exception as e:
        logger.error(f"Error executing query: {str(e)}")
        return None
    finally:
        if cursor:
            cursor.close()
        return_connection(conn)

def execute_modify(query, params=None):
    """
    Execute a database modification query (INSERT, UPDATE, DELETE).
    
    Args:
        query: SQL query string
        params: Query parameters
        
    Returns:
        Number of affected rows or None if an error occurred
    """
    conn = get_connection()
    if conn is None:
        return None
    
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute(query, params or ())
        row_count = cursor.rowcount
        conn.commit()
        return row_count
    except Exception as e:
        logger.error(f"Error executing modification query: {str(e)}")
        conn.rollback()
        return None
    finally:
        if cursor:
            cursor.close()
        return_connection(conn)

def execute_returning(query, params=None, cursor_factory=RealDictCursor):
    """
    Execute a database modification query with RETURNING clause.
    
    Args:
        query: SQL query string
        params: Query parameters
        cursor_factory: Cursor factory to use
        
    Returns:
        Query results or None if an error occurred
    """
    conn = get_connection()
    if conn is None:
        return None
    
    cursor = None
    try:
        cursor = conn.cursor(cursor_factory=cursor_factory)
        cursor.execute(query, params or ())
        results = cursor.fetchall()
        conn.commit()
        return results
    except Exception as e:
        logger.error(f"Error executing returning query: {str(e)}")
        conn.rollback()
        return None
    finally:
        if cursor:
            cursor.close()
        return_connection(conn)