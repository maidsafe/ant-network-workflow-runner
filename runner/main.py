import argparse
import json
import logging
import os
import sqlite3
import sys
from datetime import datetime
from typing import Dict

import requests
import yaml

from runner.workflows import NodeType, StopNodesWorkflowRun, UpgradeNodeManagerWorkflow
from runner.db import list_workflow_runs

REPO_OWNER = "maidsafe"
REPO_NAME = "sn-testnet-workflows"
STOP_NODES_WORKFLOW_ID = 126356854
UPGRADE_NODE_MANAGER_WORKFLOW_ID = 109612531

def get_github_token() -> str:
    """Get GitHub token from environment variable."""
    token = os.getenv("WORKFLOW_RUNNER_PAT")
    if not token:
        raise ValueError("WORKFLOW_RUNNER_PAT environment variable is not set")
    return token

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

def load_yaml_config(file_path: str) -> Dict:
    """Load and parse the YAML configuration file."""
    try:
        with open(file_path, "r") as file:
            return yaml.safe_load(file)
    except FileNotFoundError:
        print(f"Error: Config file not found at {file_path}")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"Error parsing YAML file: {e}")
        sys.exit(1)

def list_runs() -> None:
    """List all recorded workflow runs."""
    try:
        runs = list_workflow_runs()
        if not runs:
            print("No workflow runs found.")
            return
            
        for run in runs:
            workflow_name, branch_name, network_name, triggered_at, inputs = run
            timestamp = datetime.fromisoformat(triggered_at).strftime("%Y-%m-%d %H:%M:%S UTC")
            inputs_dict = json.loads(inputs)
            
            print(f"Workflow: {workflow_name}")
            print(f"Branch: {branch_name}")
            print(f"Network: {network_name}")
            print(f"Triggered: {timestamp}")
            print("Inputs:")
            for key, value in inputs_dict.items():
                print(f"  {key}: {value}")
            print("-" * 50)
    except sqlite3.Error as e:
        print(f"Error: Failed to retrieve workflow runs: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        description="CLI tool to stop testnet nodes via GitHub Actions"
    )
    
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )
    parser.add_argument(
        "--branch",
        default="main",
        help="GitHub branch name (default: main)"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    subparsers.add_parser("ls", help="List all workflow runs")
    
    stop_parser = subparsers.add_parser("stop-nodes", help="Stop testnet nodes")
    stop_parser.add_argument(
        "--path",
        required=True,
        help="Path to the inputs file"
    )

    upgrade_parser = subparsers.add_parser("upgrade-node-man", help="Upgrade node manager version")
    upgrade_parser.add_argument(
        "--path",
        required=True,
        help="Path to the inputs file"
    )

    args = parser.parse_args()
    
    if args.debug:
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
    
    if args.command == "stop-nodes":
        config = load_yaml_config(args.path)
        stop_nodes(config, args.branch)
    elif args.command == "ls":
        list_runs()
    elif args.command == "upgrade-node-man":
        config = load_yaml_config(args.path)
        upgrade_node_manager(config, args.branch)
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()
