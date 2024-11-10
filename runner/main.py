import argparse
import os
import sys
from typing import Dict
import json
from datetime import datetime
import sqlite3
import logging

import requests
import yaml

from runner.workflows import NodeType, StopNodesWorkflowRun

REPO_OWNER = "maidsafe"
REPO_NAME = "sn-testnet-workflows"
STOP_NODES_WORKFLOW_ID = 126356854

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
    
    stop_parser = subparsers.add_parser("stop-nodes", help="Stop testnet nodes")
    stop_parser.add_argument(
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
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()
