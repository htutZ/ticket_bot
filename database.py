import os
import psycopg2
from psycopg2 import sql
from urllib.parse import urlparse

DATABASE_URL = os.getenv("DATABASE_URL")

def get_conn():
    """Establish connection to PostgreSQL"""
    conn = psycopg2.connect(DATABASE_URL, sslmode="require")
    return conn

def init_db():
    """Initialize database tables"""
    conn = get_conn()
    cursor = conn.cursor()
    
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

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_ticket_status 
        ON tickets(status)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_updates_ticket_id 
        ON ticket_updates(ticket_id)
    """)

    conn.commit()
    conn.close()

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