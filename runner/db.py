import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict
import os

DB_PATH = Path.home() / ".local" / "share" / "safe" / "workflow_runs.db"

def init_db() -> None:
    """Initialize the database and create the workflow_runs table if it doesn't exist."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS workflow_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workflow_name TEXT NOT NULL,
                branch_name TEXT NOT NULL,
                network_name TEXT NOT NULL,
                triggered_at TIMESTAMP NOT NULL,
                inputs JSON NOT NULL
            )
        """)
        conn.commit()
    finally:
        conn.close()

def record_workflow_run(
    """
    Record a workflow run in the database.
    
    Args:
        workflow_name: Name of the workflow being executed
        network_name: Name of the network being operated on
        inputs: Dictionary containing all workflow inputs
    """
    init_db()
    
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO workflow_runs (workflow_name, branch_name, network_name, triggered_at, inputs)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                workflow_name,
                branch_name,
                network_name,
                datetime.utcnow().isoformat(),
                json.dumps(inputs)
            )
        )
        conn.commit()
    finally:
        conn.close()
