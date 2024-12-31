# This module seems pointless, but it exists to remove an issue with circular referencing between
# the models and the db modules.
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DB_PATH = Path.home() / ".local" / "share" / "autonomi" / "workflow_runs2.db"
DB_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DB_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """
    Get a database session. Creates database and tables if they don't exist.
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close() 