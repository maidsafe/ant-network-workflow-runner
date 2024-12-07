import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

DB_PATH = Path.home() / ".local" / "share" / "safe" / "workflow_runs.db"
DB_PATH = Path.home() / ".local" / "share" / "autonomi" / "workflow_runs.db"

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
                ant_version TEXT,
                antnode_version TEXT,
                antctl_version TEXT,
                branch TEXT,
                repo_owner TEXT,
                chunk_size INTEGER,
                antnode_features TEXT,
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
                max_log_files INTEGER,
                max_archived_log_files INTEGER,
                evm_data_payments_address TEXT,
                evm_payment_token_address TEXT,
                evm_rpc_url TEXT,
                related_pr INTEGER,
                FOREIGN KEY (workflow_run_id) REFERENCES workflow_runs(id)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS comparisons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                test_id INTEGER NOT NULL,
                ref_id INTEGER NOT NULL,
                thread_link TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL,
                report TEXT,
                result_recorded_at TIMESTAMP,
                FOREIGN KEY (test_id) REFERENCES deployments(id),
                FOREIGN KEY (ref_id) REFERENCES deployments(id)
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
        
        antnode_features = config.get("antnode-features")
        if isinstance(antnode_features, list):
            antnode_features = ",".join(antnode_features)
            
        cursor.execute(
            """
            INSERT INTO deployments (
                workflow_run_id, name, ant_version,
                antnode_version, antctl_version, branch,
                repo_owner, chunk_size, antnode_features,
                bootstrap_node_count, generic_node_count, private_node_count,
                downloader_count, uploader_count, bootstrap_vm_count,
                generic_vm_count, private_vm_count, uploader_vm_count,
                bootstrap_node_vm_size, generic_node_vm_size, private_node_vm_size,
                uploader_vm_size, evm_network_type, rewards_address,
                max_log_files, max_archived_log_files, evm_data_payments_address,
                evm_payment_token_address, evm_rpc_url, related_pr
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                workflow_run_id,
                config["network-name"],
                config.get("ant-version"),
                config.get("antnode-version"),
                config.get("antctl-version"),
                config.get("branch"),
                config.get("repo-owner"),
                config.get("chunk-size"),
                antnode_features,
                config.get("bootstrap-node-count", defaults["bootstrap_node_count"]),
                config.get("generic-node-count", defaults["generic_node_count"]),
                config.get("private-node-count", defaults["private_node_count"]),
                config.get("downloader-count", defaults["downloader_count"]),
                config.get("uploader-count", defaults["uploader_count"]),
                config.get("bootstrap-vm-count", defaults["bootstrap_vm_count"]),
                config.get("generic-vm-count", defaults["generic_vm_count"]),
                config.get("private-vm-count", defaults["private_vm_count"]),
                config.get("uploader-vm-count", defaults["uploader_vm_count"]),
                config.get("bootstrap-node-vm-size", defaults["bootstrap_node_vm_size"]),
                config.get("node-vm-size", defaults["generic_node_vm_size"]),
                config.get("node-vm-size", defaults["private_node_vm_size"]),
                config.get("uploader-vm-size", defaults["uploader_vm_size"]),
                config.get("evm-network-type", "custom"),
                config["rewards-address"],
                config.get("max-log-files"),
                config.get("max-archived-log-files"),
                config.get("evm-data-payments-address"),
                config.get("evm-payment-token-address"),
                config.get("evm-rpc-url"),
                config.get("related-pr")
            )
        )
        conn.commit()
    finally:
        conn.close()

def list_deployments() -> list:
    """
    Retrieve all deployments from the database, joined with their workflow runs.
    
    Returns:
        List of tuples containing deployment information joined with workflow run data
    """
    init_db()
    
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                d.*,
                w.triggered_at,
                w.run_id
            FROM deployments d
            JOIN workflow_runs w ON d.workflow_run_id = w.run_id
            ORDER BY w.triggered_at ASC
        """)
        return cursor.fetchall()
    finally:
        conn.close()

def create_comparison(test_id: int, ref_id: int, thread_link: str) -> None:
    """
    Create a new comparison record in the database.
    
    Args:
        test_id: ID of the test deployment
        ref_id: ID of the reference deployment
        thread_link: Link to the comparison thread
    """
    init_db()
    
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO comparisons 
            (test_id, ref_id, thread_link, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                test_id,
                ref_id,
                thread_link,
                datetime.utcnow().isoformat()
            )
        )
        conn.commit()
    finally:
        conn.close()

def validate_comparison_deployment_ids(test_id: int, ref_id: int) -> None:
    """
    Validate that both deployment IDs exist in the database.
    
    Args:
        test_id: ID of the test deployment
        ref_id: ID of the reference deployment
        
    Raises:
        ValueError: If one or both deployment IDs don't exist
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM deployments WHERE id IN (?, ?)", (test_id, ref_id))
        count = cursor.fetchone()[0]
        
        if count != 2:
            raise ValueError(f"One or both deployment IDs ({test_id}, {ref_id}) do not exist")
    finally:
        conn.close()

def list_comparisons() -> list:
    """
    Retrieve all comparisons from the database, joined with deployment names.
    
    Returns:
        List of tuples containing (test_name, ref_name, thread_link)
    """
    init_db()
    
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                c.id,
                test.name as test_name,
                ref.name as ref_name,
                c.thread_link
            FROM comparisons c
            JOIN deployments test ON c.test_id = test.id
            JOIN deployments ref ON c.ref_id = ref.id
            ORDER BY c.created_at ASC
        """)
        return cursor.fetchall()
    finally:
        conn.close()
