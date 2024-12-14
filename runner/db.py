import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from runner.models import Comparison, Deployment, ComparisonSummary

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
                peer_cache_node_count INTEGER NOT NULL,
                generic_node_count INTEGER NOT NULL,
                private_node_count INTEGER NOT NULL,
                downloader_count INTEGER NOT NULL,
                uploader_count INTEGER NOT NULL,
                peer_cache_vm_count INTEGER NOT NULL,
                generic_vm_count INTEGER NOT NULL,
                private_vm_count INTEGER NOT NULL,
                uploader_vm_count INTEGER NOT NULL,
                peer_cache_node_vm_size TEXT NOT NULL,
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
                network_id INTEGER,
                FOREIGN KEY (workflow_run_id) REFERENCES workflow_runs(id)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS comparisons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                test_id INTEGER NOT NULL,
                ref_id INTEGER NOT NULL,
                thread_link TEXT,
                created_at TIMESTAMP NOT NULL,
                report TEXT,
                result_recorded_at TIMESTAMP,
                started_at TIMESTAMP,
                ended_at TIMESTAMP,
                ref_version TEXT,
                test_version TEXT,
                passed BOOLEAN,
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

def record_deployment(workflow_run_id: int, config: Dict[str, Any], defaults: Dict[str, Any], is_legacy: bool = False) -> None:
    """
    Record a deployment in the database.
    
    Args:
        workflow_run_id: ID of the associated workflow run
        config: Dictionary containing deployment configuration
        defaults: Dictionary containing default values for the environment type
        is_legacy: Whether the deployment is a legacy deployment
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        
        ant_version = config.get("autonomi-version" if is_legacy else "ant-version")
        antnode_version = config.get("safenode-version" if is_legacy else "antnode-version")
        antctl_version = config.get("safenode-manager-version" if is_legacy else "antctl-version")

        features = config.get("safenode-features" if is_legacy else "antnode-features")
        if isinstance(features, list):
            features = ",".join(features)
            
        cursor.execute(
            """
            INSERT INTO deployments (
                workflow_run_id, name, ant_version,
                antnode_version, antctl_version, branch,
                repo_owner, chunk_size, antnode_features,
                peer_cache_node_count, generic_node_count, private_node_count,
                downloader_count, uploader_count, peer_cache_vm_count,
                generic_vm_count, private_vm_count, uploader_vm_count,
                peer_cache_node_vm_size, generic_node_vm_size, private_node_vm_size,
                uploader_vm_size, evm_network_type, rewards_address,
                max_log_files, max_archived_log_files, evm_data_payments_address,
                evm_payment_token_address, evm_rpc_url, related_pr, network_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                workflow_run_id,
                config["network-name"],
                ant_version,
                antnode_version,
                antctl_version,
                config.get("branch"),
                config.get("repo-owner"),
                config.get("chunk-size"),
                features,
                config.get("peer-cache-node-count", defaults["peer_cache_node_count"]),
                config.get("generic-node-count", defaults["generic_node_count"]),
                config.get("private-node-count", defaults["private_node_count"]),
                config.get("downloader-count", defaults["downloader_count"]),
                config.get("uploader-count", defaults["uploader_count"]),
                config.get("peer-cache-vm-count", defaults["peer_cache_vm_count"]),
                config.get("generic-vm-count", defaults["generic_vm_count"]),
                config.get("private-vm-count", defaults["private_vm_count"]),
                config.get("uploader-vm-count", defaults["uploader_vm_count"]),
                config.get("peer-cache-node-vm-size", defaults["peer_cache_node_vm_size"]),
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
                config.get("related-pr"),
                config.get("network-id") if not is_legacy else None
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

def create_comparison(test_id: int, ref_id: int, ref_version: Optional[str] = None, test_version: Optional[str] = None) -> None:
    """
    Create a new comparison record in the database.
    
    Args:
        test_id: ID of the test deployment
        ref_id: ID of the reference deployment
        ref_version: Optional reference version string
        test_version: Optional test version string
    """
    init_db()
    
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO comparisons 
            (test_id, ref_id, created_at, ref_version, test_version)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                test_id,
                ref_id,
                datetime.utcnow().isoformat(),
                ref_version,
                test_version
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

def list_comparisons() -> list[ComparisonSummary]:
    """
    Retrieve all comparisons from the database, joined with deployment names.
    
    Returns:
        List of ComparisonSummary objects containing summary information about each comparison
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
                c.thread_link,
                c.passed,
                c.created_at,
                c.result_recorded_at
            FROM comparisons c
            JOIN deployments test ON c.test_id = test.id
            JOIN deployments ref ON c.ref_id = ref.id
            ORDER BY c.created_at ASC
        """)
        return [
            ComparisonSummary(
                id=row[0],
                test_name=row[1],
                ref_name=row[2],
                thread_link=row[3],
                passed=row[4],
                created_at=datetime.fromisoformat(row[5]),
                result_recorded_at=datetime.fromisoformat(row[6]) if row[6] else None
            )
            for row in cursor.fetchall()
        ]
    finally:
        conn.close()

def get_deployment_by_id(cursor: sqlite3.Cursor, deployment_id: int) -> Deployment:
    """
    Retrieve a deployment by its ID.
    
    Args:
        cursor: Database cursor
        deployment_id: ID of the deployment to retrieve
        
    Returns:
        Deployment: The deployment record
        
    Raises:
        ValueError: If deployment with given ID is not found
    """
    cursor.execute("""
        SELECT 
            d.*,
            w.triggered_at,
            w.run_id
        FROM deployments d
        JOIN workflow_runs w ON d.workflow_run_id = w.run_id
        WHERE d.id = ?
    """, (deployment_id,))
    
    row = cursor.fetchone()
    if not row:
        raise ValueError(f"Deployment with ID {deployment_id} not found")
        
    return Deployment(
        id=row[0],
        name=row[2],
        ant_version=row[3],
        antnode_version=row[4],
        antctl_version=row[5],
        branch=row[6],
        repo_owner=row[7],
        chunk_size=row[8],
        antnode_features=row[9],
        peer_cache_node_count=row[10],
        generic_node_count=row[11],
        private_node_count=row[12],
        downloader_count=row[13],
        uploader_count=row[14],
        peer_cache_vm_count=row[15],
        generic_vm_count=row[16],
        private_vm_count=row[17],
        uploader_vm_count=row[18],
        peer_cache_node_vm_size=row[19],
        generic_node_vm_size=row[20],
        private_node_vm_size=row[21],
        uploader_vm_size=row[22],
        evm_network_type=row[23],
        rewards_address=row[24],
        max_log_files=row[25],
        max_archived_log_files=row[26],
        evm_data_payments_address=row[27],
        evm_payment_token_address=row[28],
        evm_rpc_url=row[29],
        related_pr=row[30],
        network_id=row[31],
        triggered_at=datetime.fromisoformat(row[32]),
        run_id=row[33]
    )

def get_comparison(comparison_id: int) -> Comparison:
    """
    Retrieve a comparison and its associated deployments by ID.
    
    Args:
        comparison_id: ID of the comparison to retrieve
        
    Returns:
        Comparison: The comparison record
        
    Raises:
        ValueError: If comparison with given ID is not found
    """
    init_db()
    
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, test_id, ref_id, thread_link, created_at, report, result_recorded_at,
                started_at, ended_at, ref_version, test_version, passed
            FROM comparisons
            WHERE id = ?
        """, (comparison_id,))
        
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Comparison with ID {comparison_id} not found")
            
        test_deployment = get_deployment_by_id(cursor, row[1])
        ref_deployment = get_deployment_by_id(cursor, row[2])
            
        return Comparison(
            id=row[0],
            test_deployment=test_deployment,
            ref_deployment=ref_deployment,
            thread_link=row[3],
            created_at=datetime.fromisoformat(row[4]),
            report=row[5],
            result_recorded_at=datetime.fromisoformat(row[6]) if row[6] else None,
            started_at=datetime.fromisoformat(row[7]) if row[7] else None,
            ended_at=datetime.fromisoformat(row[8]) if row[8] else None,
            ref_version=row[9] if row[9] else None,
            test_version=row[10] if row[10] else None,
            passed=row[11] if row[11] else None
        )
    finally:
        conn.close()

def update_comparison_thread_link(comparison_id: int, thread_link: str) -> None:
    """
    Update the thread link for a comparison.
    
    Args:
        comparison_id: ID of the comparison to update
        thread_link: URL of the thread where the comparison was posted
        
    Raises:
        ValueError: If comparison with given ID is not found
    """
    init_db()
    
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE comparisons
            SET thread_link = ?
            WHERE id = ?
            """,
            (thread_link, comparison_id)
        )
        
        if cursor.rowcount == 0:
            raise ValueError(f"Comparison with ID {comparison_id} not found")
            
        conn.commit()
    finally:
        conn.close()

def update_comparison_results(comparison_id: int, started_at: str, ended_at: str, report_content: str, passed: bool) -> None:
    """
    Update a comparison record with results data.
    
    Args:
        comparison_id: ID of the comparison to update
        started_at: ISO format timestamp for when the comparison started
        ended_at: ISO format timestamp for when the comparison ended
        report_content: HTML content of the report
        passed: Boolean indicating if the comparison passed (True) or failed (False)
        
    Raises:
        ValueError: If comparison with given ID is not found
    """
    init_db()
    
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE comparisons
            SET started_at = ?, ended_at = ?, report = ?, result_recorded_at = ?, passed = ?
            WHERE id = ?
            """,
            (
                started_at,
                ended_at,
                report_content,
                datetime.utcnow().isoformat(),
                passed,
                comparison_id
            )
        )
        
        if cursor.rowcount == 0:
            raise ValueError(f"Comparison with ID {comparison_id} not found")
            
        conn.commit()
    finally:
        conn.close()
