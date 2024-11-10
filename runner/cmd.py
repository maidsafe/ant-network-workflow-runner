import json
import sqlite3
import os
import sys
from datetime import datetime
from typing import Dict

import requests

from runner.db import list_workflow_runs
from runner.workflows import NodeType, StopNodesWorkflowRun, UpgradeNodeManagerWorkflow, DestroyNetworkWorkflow

REPO_OWNER = "maidsafe"
REPO_NAME = "sn-testnet-workflows"
STOP_NODES_WORKFLOW_ID = 126356854
UPGRADE_NODE_MANAGER_WORKFLOW_ID = 109612531
DESTROY_NETWORK_WORKFLOW_ID = 63357826

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
                workflow_name, branch_name, network_name, triggered_at, inputs = run
                timestamp = datetime.fromisoformat(triggered_at).strftime("%Y-%m-%d %H:%M:%S")
                inputs_dict = json.loads(inputs)
                
                print(f"Workflow: {workflow_name}")
                print(f"Triggered: {timestamp}")
                print(f"Network: {network_name}")
                print(f"Branch: {branch_name}")
                print("Inputs:")
                for key, value in inputs_dict.items():
                    print(f"  {key}: {value}")
                print("-" * 50)
        else:
            print(f"{'Triggered':<20} {'Workflow':<25} {'Network':<15}")
            print("-" * 60)
            
            for run in runs:
                workflow_name, _, network_name, triggered_at, _ = run
                timestamp = datetime.fromisoformat(triggered_at).strftime("%Y-%m-%d %H:%M:%S")
                print(f"{timestamp:<20} {workflow_name:<25} {network_name:<15}")
        
        print("\nAll times are in UTC")
                
    except sqlite3.Error as e:
        print(f"Error: Failed to retrieve workflow runs: {e}")
        sys.exit(1)

def stop_nodes(config: Dict, branch_name: str) -> None:
    """
    Execute the stop-nodes command using the provided configuration.
    Creates and runs a StopNodesWorkflowRun instance to trigger the GitHub Actions workflow.
    """
    try:
        if "network-name" not in config:
            raise KeyError("network-name")
            
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
            testnet_deploy_args=config.get("testnet-deploy-args")
        )
        
        print(f"Dispatching the {workflow.name} workflow...")
        workflow.run()
        print("Workflow was dispatched with the following inputs:")
        for key, value in workflow.get_workflow_inputs().items():
            print(f"  {key}: {value}")
    except KeyError as e:
        print(f"Error: Missing required configuration field: {e}")
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"Error: Failed to trigger workflow: {e}")
        sys.exit(1)
    except ValueError as e:
        print(f"Error: Invalid configuration value: {e}")
        sys.exit(1)

def upgrade_node_manager(config: Dict, branch_name: str) -> None:
    """
    Execute the upgrade-node-man command using the provided configuration.
    Creates and runs an UpgradeNodeManagerWorkflow instance to trigger the GitHub Actions workflow.
    """
    try:
        if "network-name" not in config:
            raise KeyError("network-name")
        if "version" not in config:
            raise KeyError("version")
            
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
            testnet_deploy_args=config.get("testnet-deploy-args")
        )
        
        print(f"Dispatching the {workflow.name} workflow...")
        workflow.run()
        print("Workflow was dispatched with the following inputs:")
        for key, value in workflow.get_workflow_inputs().items():
            print(f"  {key}: {value}")
    except KeyError as e:
        print(f"Error: Missing required configuration field: {e}")
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"Error: Failed to trigger workflow: {e}")
        sys.exit(1)
    except ValueError as e:
        print(f"Error: Invalid configuration value: {e}")
        sys.exit(1)

def destroy_network(config: Dict, branch_name: str) -> None:
    """
    Execute the destroy-network command using the provided configuration.
    Creates and runs a DestroyNetworkWorkflow instance to trigger the GitHub Actions workflow.
    """
    try:
        if "network-name" not in config:
            raise KeyError("network-name")
            
        workflow = DestroyNetworkWorkflow(
            owner=REPO_OWNER,
            repo=REPO_NAME,
            id=DESTROY_NETWORK_WORKFLOW_ID,
            personal_access_token=get_github_token(),
            branch_name=branch_name,
            network_name=config["network-name"],
            testnet_deploy_args=config.get("testnet-deploy-args")
        )
        
        print(f"Dispatching the {workflow.name} workflow...")
        workflow.run()
        print("Workflow was dispatched with the following inputs:")
        for key, value in workflow.get_workflow_inputs().items():
            print(f"  {key}: {value}")
    except KeyError as e:
        print(f"Error: Missing required configuration field: {e}")
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"Error: Failed to trigger workflow: {e}")
        sys.exit(1)
    except ValueError as e:
        print(f"Error: Invalid configuration value: {e}")
        sys.exit(1)