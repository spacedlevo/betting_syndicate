"""
Database connection and session management for the betting syndicate.

This module sets up the SQLite database connection using SQLAlchemy.
"""

from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# Database file path
DATABASE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "database")
DATABASE_PATH = os.path.join(DATABASE_DIR, "betting_syndicate.db")

# Ensure database directory exists
os.makedirs(DATABASE_DIR, exist_ok=True)

# Create SQLite database URL
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

# Create engine with foreign key support
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},  # Needed for SQLite
    echo=False  # Set to True for SQL query logging during development
)

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Base class for ORM models
Base = declarative_base()


def get_db():
    """
    Dependency function to get database session.
    Use this in FastAPI routes to get a database session.

    Example:
        @app.get("/")
        def read_root(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Initialize the database by creating all tables.
    This should be called once when the application starts.
    """
    # Import models to ensure they're registered with Base
    from app import models

    # Create all tables
    Base.metadata.create_all(bind=engine)

    # Migrate: add audit columns to bank_transactions if missing
    with engine.connect() as conn:
        for col_sql in [
            "ALTER TABLE bank_transactions ADD COLUMN is_disregarded BOOLEAN NOT NULL DEFAULT 0",
            "ALTER TABLE bank_transactions ADD COLUMN ledger_entry_id INTEGER REFERENCES ledger(id)",
        ]:
            try:
                conn.execute(text(col_sql))
                conn.commit()
            except Exception:
                pass  # column already exists

    print(f"Database initialized at {DATABASE_PATH}")
