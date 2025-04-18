"""
Database Setup Enhancements for GlassRain

This module extends the database setup with tables required for the enhanced features.
"""

import logging
import os
import sys

# Ensure correct paths for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from glassrain_production.db_pool import get_connection, return_connection

# Configure logging
logger = logging.getLogger(__name__)

def setup_enhanced_database():
    """
    Create the additional tables required for enhanced features if they don't exist.
    
    Returns:
        bool: True if setup was successful, False otherwise
    """
    conn = get_connection()
    if not conn:
        logger.error("Failed to get database connection for enhanced setup")
        return False
    
    cursor = None
    success = False
    
    try:
        cursor = conn.cursor()
        
        # Create property_insights table
        logger.info("Creating property_insights table if it doesn't exist")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS property_insights (
                id SERIAL PRIMARY KEY,
                address_id INTEGER NOT NULL,
                user_id INTEGER,
                analysis_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                insights_data JSONB NOT NULL,
                UNIQUE (address_id)
            )
        """)
        
        # Create task_history table
        logger.info("Creating task_history table if it doesn't exist")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS task_history (
                id SERIAL PRIMARY KEY,
                task_id VARCHAR(64) NOT NULL,
                name VARCHAR(128) NOT NULL,
                description TEXT,
                status VARCHAR(32) NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                user_id INTEGER,
                progress FLOAT DEFAULT 0.0,
                progress_message TEXT,
                result_data JSONB,
                error_data JSONB,
                UNIQUE (task_id)
            )
        """)
        
        # Create cache_metadata table
        logger.info("Creating cache_metadata table if it doesn't exist")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cache_metadata (
                id SERIAL PRIMARY KEY,
                cache_key VARCHAR(256) NOT NULL,
                namespace VARCHAR(128),
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                hit_count INTEGER DEFAULT 0,
                UNIQUE (cache_key)
            )
        """)
        
        # Create cache_data table
        logger.info("Creating cache_data table if it doesn't exist")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cache_data (
                id SERIAL PRIMARY KEY,
                cache_key VARCHAR(256) NOT NULL,
                data_value JSONB NOT NULL,
                UNIQUE (cache_key)
            )
        """)
        
        # Create rate_limit_records table
        logger.info("Creating rate_limit_records table if it doesn't exist")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rate_limit_records (
                id SERIAL PRIMARY KEY,
                client_id VARCHAR(128) NOT NULL,
                endpoint VARCHAR(256),
                request_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Add index for rate limiting
        try:
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_rate_limit_client_time 
                ON rate_limit_records (client_id, request_time)
            """)
        except Exception as e:
            logger.warning(f"Failed to create index on rate_limit_records: {str(e)}")
        
        # Create notification_queue table
        logger.info("Creating notification_queue table if it doesn't exist")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notification_queue (
                id SERIAL PRIMARY KEY,
                user_id INTEGER,
                notification_type VARCHAR(64) NOT NULL,
                title VARCHAR(256) NOT NULL,
                message TEXT NOT NULL,
                data_context JSONB,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                scheduled_at TIMESTAMP,
                sent_at TIMESTAMP,
                status VARCHAR(32) DEFAULT 'pending',
                priority INTEGER DEFAULT 1
            )
        """)
        
        conn.commit()
        success = True
        logger.info("✅ Enhanced database setup completed successfully")
        
    except Exception as e:
        conn.rollback()
        logger.error(f"❌ Error setting up enhanced database: {str(e)}")
    finally:
        if cursor:
            cursor.close()
        return_connection(conn)
    
    return success

if __name__ == "__main__":
    # Run database setup directly when executed as a script
    setup_enhanced_database()