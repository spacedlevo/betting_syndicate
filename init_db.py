"""
Database initialization script.

Run this script to create the database and all tables.

Usage:
    python init_db.py
"""

from app.database import init_db

if __name__ == "__main__":
    print("Initializing database...")
    init_db()
    print("Database initialization complete!")
