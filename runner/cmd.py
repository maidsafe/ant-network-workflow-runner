import json
import sqlite3
import os
import sys
from datetime import datetime
from typing import Dict

import requests
from rich import print as rprint

from runner.db import list_workflow_runs
from runner.workflows import (
    NodeType,
    StopNodesWorkflowRun,
    UpgradeNodeManagerWorkflow,
    DestroyNetworkWorkflow,
    StartTelegrafWorkflow,
    StopTelegrafWorkflow,
    UpgradeNetworkWorkflow,
    UpdatePeerWorkflow,
)

REPO_OWNER = "maidsafe"
REPO_NAME = "sn-testnet-workflows"

DESTROY_NETWORK_WORKFLOW_ID = 63357826
START_TELEGRAF_WORKFLOW_ID = 113666375
STOP_NODES_WORKFLOW_ID = 126356854
STOP_TELEGRAF_WORKFLOW_ID = 109718824
UPDATE_PEER_WORKFLOW_ID = 127823614
UPGRADE_NODE_MANAGER_WORKFLOW_ID = 109612531
UPGRADE_NETWORK_WORKFLOW_ID = 109064529

def get_github_token() -> str:
    token = os.getenv("WORKFLOW_RUNNER_PAT")
    if not token:
        raise ValueError("WORKFLOW_RUNNER_PAT environment variable is not set")
    return token

def list_runs(show_details: bool = False) -> None:
    """List all recorded workflow runs."""
    try:
        runs = list_workflow_runs()
        if not runs:
            print("No workflow runs found.")
            return
            
        runs.sort(key=lambda x: x[3])
        
        print("=" * 61)
        print(" " * 18 + "W O R K F L O W   R U N S" + " " * 18)
        print("=" * 61 + "\n")
        
        if show_details:
            for run in runs:
                workflow_name, branch_name, network_name, triggered_at, inputs, run_id = run
                timestamp = datetime.fromisoformat(triggered_at).strftime("%Y-%m-%d %H:%M:%S")
                inputs_dict = json.loads(inputs)
                
                rprint(f"Workflow: [green]{workflow_name}[/green]")
                print(f"Triggered: {timestamp}")
                print(f"Network: {network_name}")
                print(f"Branch: {branch_name}")
                print(f"URL: https://github.com/{REPO_OWNER}/{REPO_NAME}/actions/runs/{run_id}")
                print("Inputs:")
                for key, value in inputs_dict.items():
                    print(f"  {key}: {value}")
                print("-" * 50)
        else:
            print(f"{'Triggered':<20} {'Workflow':<25} {'Network':<15}")
            print("-" * 60)
            
            for run in runs:
                workflow_name, _, network_name, triggered_at, _, _ = run
                timestamp = datetime.fromisoformat(triggered_at).strftime("%Y-%m-%d %H:%M:%S")
                rprint(f"{timestamp:<20} [green]{workflow_name:<25}[/green] {network_name:<15}")
        
        print("\nAll times are in UTC")
                
    except sqlite3.Error as e:
        print(f"Error: Failed to retrieve workflow runs: {e}")
        sys.exit(1)

def stop_nodes(config: Dict, branch_name: str, force: bool = False) -> None:
    if "network-name" not in config:
        raise KeyError("network-name")
    
    _print_workflow_banner()
    
    testnet_deploy_args = _build_testnet_deploy_args(config)
        
    workflow = StopNodesWorkflowRun(
        owner=REPO_OWNER,
        repo=REPO_NAME,
        id=STOP_NODES_WORKFLOW_ID,
        personal_access_token=get_github_token(),
        branch_name=branch_name,
        network_name=config["network-name"],
        ansible_forks=config.get("ansible-forks"),
        custom_inventory=config.get("custom-inventory"),
        delay=config.get("delay"),
        interval=config.get("interval"),
        node_type=NodeType(config["node-type"]) if "node-type" in config else None,
        testnet_deploy_args=testnet_deploy_args
    )
    _execute_workflow(workflow, force)

def upgrade_node_manager(config: Dict, branch_name: str, force: bool = False) -> None:
    if "network-name" not in config:
        raise KeyError("network-name")
    if "version" not in config:
        raise KeyError("version")
    
    _print_workflow_banner()
    
    testnet_deploy_args = _build_testnet_deploy_args(config)
        
    workflow = UpgradeNodeManagerWorkflow(
        owner=REPO_OWNER,
        repo=REPO_NAME,
        id=UPGRADE_NODE_MANAGER_WORKFLOW_ID,
        personal_access_token=get_github_token(),
        branch_name=branch_name,
        network_name=config["network-name"],
        version=config["version"],
        custom_inventory=config.get("custom-inventory"),
        node_type=NodeType(config["node-type"]) if "node-type" in config else None,
        testnet_deploy_args=testnet_deploy_args
    )
    _execute_workflow(workflow, force)

def destroy_network(config: Dict, branch_name: str, force: bool = False) -> None:
    if "network-name" not in config:
        raise KeyError("network-name")
    
    _print_workflow_banner()
    
    testnet_deploy_args = _build_testnet_deploy_args(config)
        
    workflow = DestroyNetworkWorkflow(
        owner=REPO_OWNER,
        repo=REPO_NAME,
        id=DESTROY_NETWORK_WORKFLOW_ID,
        personal_access_token=get_github_token(),
        branch_name=branch_name,
        network_name=config["network-name"],
        testnet_deploy_args=testnet_deploy_args
    )
    _execute_workflow(workflow, force)

def stop_telegraf(config: Dict, branch_name: str, force: bool = False) -> None:
    if "network-name" not in config:
        raise KeyError("network-name")
    
    _print_workflow_banner()
    
    testnet_deploy_args = _build_testnet_deploy_args(config)
        
    workflow = StopTelegrafWorkflow(
        owner=REPO_OWNER,
        repo=REPO_NAME,
        id=STOP_TELEGRAF_WORKFLOW_ID,
        personal_access_token=get_github_token(),
        branch_name=branch_name,
        network_name=config["network-name"],
        ansible_forks=config.get("ansible-forks"),
        custom_inventory=config.get("custom-inventory"),
        delay=config.get("delay"),
        node_type=NodeType(config["node-type"]) if "node-type" in config else None,
        testnet_deploy_args=testnet_deploy_args
    )
    _execute_workflow(workflow, force)

def upgrade_network(config: Dict, branch_name: str, force: bool = False) -> None:
    """Trigger the upgrade network workflow."""
    if "network-name" not in config:
        raise KeyError("network-name")
    if "version" not in config:
        raise KeyError("version")
    
    _print_workflow_banner()
    
    testnet_deploy_args = _build_testnet_deploy_args(config)
        
    workflow = UpgradeNetworkWorkflow(
        owner=REPO_OWNER,
        repo=REPO_NAME,
        id=UPGRADE_NETWORK_WORKFLOW_ID,
        personal_access_token=get_github_token(),
        branch_name=branch_name,
        network_name=config["network-name"],
        version=config["version"],
        ansible_forks=config.get("ansible-forks"),
        custom_inventory=config.get("custom-inventory"),
        delay=config.get("delay"),
        interval=config.get("interval"),
        node_type=NodeType(config["node-type"]) if "node-type" in config else None,
        testnet_deploy_args=testnet_deploy_args
    )
    _execute_workflow(workflow, force)

def start_telegraf(config: Dict, branch_name: str, force: bool = False) -> None:
    if "network-name" not in config:
        raise KeyError("network-name")
    
    _print_workflow_banner()
    
    testnet_deploy_args = _build_testnet_deploy_args(config)
        
    workflow = StartTelegrafWorkflow(
        owner=REPO_OWNER,
        repo=REPO_NAME,
        id=START_TELEGRAF_WORKFLOW_ID,
        personal_access_token=get_github_token(),
        branch_name=branch_name,
        network_name=config["network-name"],
        ansible_forks=config.get("ansible-forks"),
        custom_inventory=config.get("custom-inventory"),
        delay=config.get("delay"),
        node_type=NodeType(config["node-type"]) if "node-type" in config else None,
        testnet_deploy_args=testnet_deploy_args
    )
    _execute_workflow(workflow, force)

def update_peer(config: Dict, branch_name: str, force: bool = False) -> None:
    """Trigger the update peer workflow."""
    if "network-name" not in config:
        raise KeyError("network-name")
    if "peer" not in config:
        raise KeyError("peer")
    
    _print_workflow_banner()
        
    workflow = UpdatePeerWorkflow(
        owner=REPO_OWNER,
        repo=REPO_NAME,
        id=UPDATE_PEER_WORKFLOW_ID,
        personal_access_token=get_github_token(),
        branch_name=branch_name,
        network_name=config["network-name"],
        peer=config["peer"],
        custom_inventory=config.get("custom-inventory"),
        node_type=NodeType(config["node-type"]) if "node-type" in config else None
    )
    _execute_workflow(workflow, force)

def _execute_workflow(workflow, force: bool = False) -> None:
    """
    Common function to execute a workflow and handle its output and errors.
    
    Args:
        workflow: The workflow instance to execute
        force: If True, skip confirmation prompt
    """
    try:
        workflow.run(force=force)
        print("Workflow was dispatched with the following inputs:")
        for key, value in workflow.get_workflow_inputs().items():
            print(f"  {key}: {value}")
    except KeyError as e:
        print(f"Error: Missing required configuration field: {e}")
        sys.exit(1)
    except ValueError as e:
        print(f"Error: Invalid configuration value: {e}")
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"Error: Failed to trigger workflow: {e}")
        sys.exit(1)

def _print_workflow_banner() -> None:
    """Print a banner for the workflow command."""
    banner_text = "R U N  W O R K F L O W"
    total_width = 61
    padding = (total_width - len(banner_text)) // 2
    
    print("=" * total_width)
    print(" " * padding + banner_text + " " * (total_width - padding - len(banner_text)))
    print("=" * total_width + "\n")

def _build_testnet_deploy_args(config: Dict) -> str:
    """
    Build testnet-deploy-args string from config inputs.
    
    Args:
        config: Dictionary containing workflow configuration
        
    Returns:
        str: The constructed testnet-deploy-args string
        
    Raises:
        ValueError: If invalid combination of testnet-deploy inputs are provided
    """
    version = config.get("testnet-deploy-version")
    branch = config.get("testnet-deploy-branch")
    repo_owner = config.get("testnet-deploy-repo-owner")
    
    if version and (branch or repo_owner):
        raise ValueError("Cannot specify both testnet-deploy-version and testnet-deploy-branch/repo-owner")
        
    if bool(branch) != bool(repo_owner):
        raise ValueError("testnet-deploy-branch and testnet-deploy-repo-owner must be used together")
        
    if version:
        return f"--version {version}"
    elif branch and repo_owner:
        return f"--branch {branch} --repo-owner {repo_owner}"
    
    return ""