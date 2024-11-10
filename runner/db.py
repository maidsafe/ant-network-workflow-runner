import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

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
                inputs JSON NOT NULL,
                run_id INTEGER NOT NULL
            )
        """)
        conn.commit()
    finally:
        conn.close()

def record_workflow_run(
        workflow_name: str, branch_name: str, network_name: str, 
        inputs: Dict[str, Any], run_id: int) -> None:
    """
    Record a workflow run in the database.
    
    Args:
        workflow_name: Name of the workflow being executed
        network_name: Name of the network being operated on
        inputs: Dictionary containing all workflow inputs
        run_id: ID of the workflow run
    """
    init_db()
    
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO workflow_runs 
            (workflow_name, branch_name, network_name, triggered_at, inputs, run_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                workflow_name,
                branch_name,
                network_name,
                datetime.utcnow().isoformat(),
                json.dumps(inputs),
                run_id
            )
        )
        conn.commit()
    finally:
        conn.close()

def list_workflow_runs() -> list:
    """
    Retrieve all workflow runs from the database.
    
    Returns:
        List of tuples containing workflow run information
        (workflow_name, branch_name, network_name, triggered_at, inputs, run_id)
    """
    init_db()
    
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT workflow_name, branch_name, network_name, triggered_at, inputs, run_id
            FROM workflow_runs
            ORDER BY triggered_at DESC
        """)
        return cursor.fetchall()
    finally:
        conn.close()
