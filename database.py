import os
import psycopg2
import time
from psycopg2 import pool, sql
from urllib.parse import urlparse
from psycopg2.extras import RealDictCursor
import logging

DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("PG_URL") 
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Connection pool setup
connection_pool = None
def init_pool():
    global connection_pool
    try:
        db_url = os.getenv("DATABASE_URL")
        
        if not db_url:
            raise ValueError("DATABASE_URL environment variable not set")
            
        # Fix common Railway URL format issues
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        
        logger.info("Initializing connection pool...")
        connection_pool = pool.SimpleConnectionPool(
            minconn=1,
            maxconn=5,
            dsn=db_url,
            sslmode="require",
            cursor_factory=RealDictCursor
        )
        logger.info("Connection pool initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize connection pool: {e}")
        raise

def get_conn():
    retry_count = 0
    max_retries = 3
    retry_delay = 2
    
    while retry_count < max_retries:
        try:
            conn = connection_pool.getconn()
            conn.autocommit = False
            return conn
        except Exception as e:
            retry_count += 1
            logger.warning(f"Connection attempt {retry_count} failed: {e}")
            if retry_count == max_retries:
                raise
            time.sleep(retry_delay)

def return_conn(conn):
    try:
        connection_pool.putconn(conn)
    except Exception as e:
        logger.error(f"Error returning connection: {e}")

def init_db():
    conn = None
    try:
        conn = get_conn()
        cursor = conn.cursor()
        
        # Create tables with error handling
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                id SERIAL PRIMARY KEY,
                description TEXT NOT NULL,
                photo_file_id TEXT,
                status TEXT DEFAULT 'open',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ticket_updates (
                id SERIAL PRIMARY KEY,
                ticket_id INTEGER NOT NULL,
                username TEXT NOT NULL,
                update_text TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE
            )
        """)
        
        # Create indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ticket_status 
            ON tickets(status)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_updates_ticket_id 
            ON ticket_updates(ticket_id)
        """)
        
        conn.commit()
        logger.info("Database tables initialized successfully")
        
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            return_conn(conn)

def add_ticket(description, photo_file_id=None):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO tickets (description, photo_file_id) 
        VALUES (%s, %s) RETURNING id""",
        (description, photo_file_id)
    )
    ticket_id = cursor.fetchone()[0]
    conn.commit()
    conn.close()
    return ticket_id

def get_open_tickets():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, description, photo_file_id 
        FROM tickets 
        WHERE status = 'open'
        ORDER BY created_at DESC
    """)
    tickets = cursor.fetchall()
    conn.close()
    return tickets

def get_ticket(ticket_id):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, description, photo_file_id 
        FROM tickets 
        WHERE id = %s
    """, (ticket_id,))
    ticket = cursor.fetchone()
    conn.close()
    return ticket

def mark_ticket_resolved(ticket_id):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE tickets 
        SET status = 'resolved' 
        WHERE id = %s
    """, (ticket_id,))
    conn.commit()
    conn.close()

def add_ticket_update(ticket_id, username, update_text):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO ticket_updates (ticket_id, username, update_text) 
        VALUES (%s, %s, %s)
    """, (ticket_id, username, update_text))
    conn.commit()
    conn.close()

def get_ticket_updates(ticket_id):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT update_text, username, created_at 
        FROM ticket_updates 
        WHERE ticket_id = %s 
        ORDER BY created_at
    """, (ticket_id,))
    updates = cursor.fetchall()
    conn.close()
    return updates