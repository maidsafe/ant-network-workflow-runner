import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

DB_PATH = Path.home() / ".local" / "share" / "safe" / "workflow_runs.db"

def init_db() -> None:
    """Initialize the database and create the required tables if they don't exist."""
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
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS deployments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workflow_run_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                autonomi_version TEXT,
                safenode_version TEXT,
                safenode_manager_version TEXT,
                branch TEXT,
                repo_owner TEXT,
                chunk_size INTEGER,
                safenode_features TEXT,
                bootstrap_node_count INTEGER NOT NULL,
                generic_node_count INTEGER NOT NULL,
                private_node_count INTEGER NOT NULL,
                downloader_count INTEGER NOT NULL,
                uploader_count INTEGER NOT NULL,
                bootstrap_vm_count INTEGER NOT NULL,
                generic_vm_count INTEGER NOT NULL,
                private_vm_count INTEGER NOT NULL,
                uploader_vm_count INTEGER NOT NULL,
                bootstrap_node_vm_size TEXT NOT NULL,
                generic_node_vm_size TEXT NOT NULL,
                private_node_vm_size TEXT NOT NULL,
                uploader_vm_size TEXT NOT NULL,
                evm_network_type TEXT NOT NULL,
                rewards_address TEXT NOT NULL,
                FOREIGN KEY (workflow_run_id) REFERENCES workflow_runs(id)
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

def record_deployment(workflow_run_id: int, config: Dict[str, Any], defaults: Dict[str, Any]) -> None:
    """
    Record a deployment in the database.
    
    Args:
        workflow_run_id: ID of the associated workflow run
        config: Dictionary containing deployment configuration
        defaults: Dictionary containing default values for the environment type
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO deployments (
                workflow_run_id, name, autonomi_version, safenode_version,
                safenode_manager_version, branch, repo_owner, chunk_size,
                safenode_features, bootstrap_node_count, generic_node_count,
                private_node_count, downloader_count, uploader_count,
                bootstrap_vm_count, generic_vm_count, private_vm_count,
                uploader_vm_count, bootstrap_node_vm_size, generic_node_vm_size,
                private_node_vm_size, uploader_vm_size, evm_network_type,
                rewards_address
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                workflow_run_id,
                config['network-name'],
                config.get('autonomi-version'),
                config.get('safenode-version'),
                config.get('safenode-manager-version'),
                config.get('branch'),
                config.get('repo-owner'),
                config.get('chunk-size'),
                ','.join(config['safenode-features']) if config.get('safenode-features') else None,
                config.get('bootstrap-node-count', defaults['bootstrap_node_count']),
                config.get('generic-node-count', defaults['generic_node_count']),
                config.get('private-node-count', defaults['private_node_count']),
                config.get('downloader-count', defaults['downloader_count']),
                config.get('uploader-count', defaults['uploader_count']),
                config.get('bootstrap-vm-count', defaults['bootstrap_vm_count']),
                config.get('generic-vm-count', defaults['generic_vm_count']),
                config.get('private-vm-count', defaults['private_vm_count']),
                config.get('uploader-vm-count', defaults['uploader_vm_count']),
                config.get('bootstrap-node-vm-size', defaults['bootstrap_node_vm_size']),
                config.get('node-vm-size', defaults['generic_node_vm_size']),
                config.get('node-vm-size', defaults['private_node_vm_size']),
                config.get('uploader-vm-size', defaults['uploader_vm_size']),
                config.get('evm-network-type', 'custom'),
                config['rewards-address']
            )
        )
        conn.commit()
    finally:
        conn.close()
