import sqlite3
from datetime import datetime

def init_db():
    conn = sqlite3.connect("tickets.db")
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            description TEXT NOT NULL,
            photo_file_id TEXT,
            status TEXT DEFAULT 'open',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ticket_updates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            update_text TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE
        )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ticket_status ON tickets(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_updates_ticket_id ON ticket_updates(ticket_id)")

    conn.commit()
    conn.close()

def add_ticket(description, photo_file_id=None):
    conn = sqlite3.connect("tickets.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO tickets (description, photo_file_id) VALUES (?, ?)", 
        (description, photo_file_id)
    )
    ticket_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return ticket_id

def get_open_tickets():
    conn = sqlite3.connect("tickets.db")
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
    conn = sqlite3.connect("tickets.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, description, photo_file_id 
        FROM tickets 
        WHERE id = ?
    """, (ticket_id,))
    ticket = cursor.fetchone()
    conn.close()
    return ticket

def mark_ticket_resolved(ticket_id):
    conn = sqlite3.connect("tickets.db")
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE tickets 
        SET status = 'resolved' 
        WHERE id = ?
    """, (ticket_id,))
    conn.commit()
    conn.close()

def add_ticket_update(ticket_id, username, update_text):
    conn = sqlite3.connect("tickets.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO ticket_updates (ticket_id, username, update_text) 
        VALUES (?, ?, ?)
    """, (ticket_id, username, update_text))
    conn.commit()
    conn.close()

def get_ticket_updates(ticket_id):
    conn = sqlite3.connect("tickets.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT update_text, username, created_at 
        FROM ticket_updates 
        WHERE ticket_id = ? 
        ORDER BY created_at
    """, (ticket_id,))
    updates = cursor.fetchall()
    conn.close()
    return updates