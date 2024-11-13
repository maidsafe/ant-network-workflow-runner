import argparse
import logging
import sys
from typing import Dict

import yaml

from runner import cmd
from runner.workflows import confirm_workflow_dispatch

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
    
    ls_parser = subparsers.add_parser("ls", help="List all workflow runs")
    ls_parser.add_argument(
        "--details",
        action="store_true",
        help="Show detailed information for each workflow run"
    )
    
    stop_parser = subparsers.add_parser("stop-nodes", help="Stop testnet nodes")
    stop_parser.add_argument(
        "--path",
        required=True,
        help="Path to the inputs file"
    )
    stop_parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompt before dispatching workflow"
    )

    upgrade_parser = subparsers.add_parser("upgrade-node-man", help="Upgrade node manager version")
    upgrade_parser.add_argument(
        "--path",
        required=True,
        help="Path to the inputs file"
    )
    upgrade_parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompt before dispatching workflow"
    )

    destroy_parser = subparsers.add_parser("destroy-network", help="Destroy a testnet network")
    destroy_parser.add_argument(
        "--path",
        required=True,
        help="Path to the inputs file"
    )
    destroy_parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompt before dispatching workflow"
    )

    stop_telegraf_parser = subparsers.add_parser("stop-telegraf", help="Stop telegraf on testnet nodes")
    stop_telegraf_parser.add_argument(
        "--path",
        required=True,
        help="Path to the inputs file"
    )
    stop_telegraf_parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompt before dispatching workflow"
    )

    args = parser.parse_args()
    
    if args.debug:
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
    
    if args.command == "stop-nodes":
        config = load_yaml_config(args.path)
        cmd.stop_nodes(config, args.branch, args.force)
    elif args.command == "ls":
        cmd.list_runs(show_details=args.details)
    elif args.command == "upgrade-node-man":
        config = load_yaml_config(args.path)
        cmd.upgrade_node_manager(config, args.branch, args.force)
    elif args.command == "destroy-network":
        config = load_yaml_config(args.path)
        cmd.destroy_network(config, args.branch, args.force)
    elif args.command == "stop-telegraf":
        config = load_yaml_config(args.path)
        cmd.stop_telegraf(config, args.branch, args.force)
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()