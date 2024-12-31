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
            config = yaml.safe_load(file)
        if "evm-data-payments-address" in config and isinstance(config["evm-data-payments-address"], int):
            config["evm-data-payments-address"] = f"0x{config['evm-data-payments-address']:040x}"
        if "evm-payment-token-address" in config and isinstance(config["evm-payment-token-address"], int):
            config["evm-payment-token-address"] = f"0x{config['evm-payment-token-address']:040x}"
        if "rewards-address" in config and isinstance(config["rewards-address"], int):
            config["rewards-address"] = f"0x{config['rewards-address']:040x}"
        return config
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

    bootstrap_network_parser = subparsers.add_parser("bootstrap-network", help="Bootstrap a new network")
    bootstrap_network_parser.add_argument(
        "--path",
        required=True,
        help="Path to the inputs file"
    )
    bootstrap_network_parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompt before dispatching workflow"
    )

    comparisons_parser = subparsers.add_parser("comparisons", help="Manage deployment comparisons")
    comparisons_subparsers = comparisons_parser.add_subparsers(dest="comparisons_command", help="Available comparison commands")
    
    comparisons_subparsers.add_parser("new", help="Create a new comparison")
    comparisons_subparsers.add_parser("ls", help="List all comparisons")
    
    comparisons_print_parser = comparisons_subparsers.add_parser("print", help="Print details of a specific comparison")
    comparisons_print_parser.add_argument(
        "--id",
        type=int,
        required=True,
        help="ID of the comparison to print"
    )
    
    add_thread_parser = comparisons_subparsers.add_parser("add-thread", help="Add thread link to a comparison")
    add_thread_parser.add_argument(
        "--id",
        type=int,
        required=True,
        help="ID of the comparison"
    )
    add_thread_parser.add_argument(
        "--link",
        type=str,
        required=True,
        help="URL of the thread where the comparison was posted"
    )
    
    record_results_parser = comparisons_subparsers.add_parser("record-results", help="Record comparison results")
    record_results_parser.add_argument(
        "--id",
        type=int,
        required=True,
        help="ID of the comparison"
    )
    record_results_parser.add_argument(
        "--start",
        type=str,
        required=True,
        help="Start timestamp of the comparison"
    )
    record_results_parser.add_argument(
        "--end",
        type=str,
        required=True,
        help="End timestamp of the comparison"
    )
    record_results_parser.add_argument(
        "--path",
        type=str,
        required=True,
        help="Path to the HTML report file"
    )
    record_results_parser.add_argument(
        "--pass",
        dest="passed",
        action="store_true",
        help="Mark the comparison as passed"
    )
    
    comparisons_post_parser = comparisons_subparsers.add_parser("post", help="Post a comparison report to Slack")
    comparisons_post_parser.add_argument(
        "--id",
        type=int,
        required=True,
        help="ID of the comparison to post"
    )
    
    deployment_parser = subparsers.add_parser("deployment", help="Manage deployments")
    deployment_subparsers = deployment_parser.add_subparsers(dest="deployment_command", help="Available deployment commands")
    
    deployment_ls_parser = deployment_subparsers.add_parser("ls", help="List all deployments")
    deployment_ls_parser.add_argument(
        "--details",
        action="store_true",
        help="Show detailed information for each deployment"
    )

    deployment_smoke_test_parser = deployment_subparsers.add_parser(
        "smoke-test", 
        help="Run a smoke test for a deployment"
    )
    deployment_smoke_test_parser.add_argument(
        "--id",
        type=int,
        required=True,
        help="ID of the deployment to test"
    )

    deposit_funds_parser = subparsers.add_parser("deposit-funds", help="Deposit funds to network nodes")
    deposit_funds_parser.add_argument(
        "--path",
        required=True,
        help="Path to the inputs file"
    )
    deposit_funds_parser.add_argument(
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

    drain_funds_parser = subparsers.add_parser("drain-funds", help="Drain funds from network nodes")
    drain_funds_parser.add_argument(
        "--path",
        required=True,
        help="Path to the inputs file"
    )
    drain_funds_parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompt before dispatching workflow"
    )

    kill_droplets_parser = subparsers.add_parser("kill-droplets", help="Kill specified droplets")
    kill_droplets_parser.add_argument(
        "--path",
        required=True,
        help="Path to the inputs file"
    )
    kill_droplets_parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompt before dispatching workflow"
    )

    launch_legacy_network_parser = subparsers.add_parser("launch-legacy-network", help="Launch a new legacy network")
    launch_legacy_network_parser.add_argument(
        "--path",
        required=True,
        help="Path to the inputs file"
    )
    launch_legacy_network_parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompt before dispatching workflow"
    )

    launch_network_parser = subparsers.add_parser("launch-network", help="Launch a new network")
    launch_network_parser.add_argument(
        "--path",
        required=True,
        help="Path to the inputs file"
    )
    launch_network_parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompt before dispatching workflow"
    )

    ls_parser = subparsers.add_parser("ls", help="List all workflow runs")
    ls_parser.add_argument(
        "--details",
        action="store_true",
        help="Show detailed information for each workflow run"
    )

    network_status_parser = subparsers.add_parser("network-status", help="Check status of testnet nodes")
    network_status_parser.add_argument(
        "--path",
        required=True,
        help="Path to the inputs file"
    )
    network_status_parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompt before dispatching workflow"
    )

    start_nodes_parser = subparsers.add_parser("start-nodes", help="Start testnet nodes")
    start_nodes_parser.add_argument(
        "--path",
        required=True,
        help="Path to the inputs file"
    )
    start_nodes_parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompt before dispatching workflow"
    )

    start_telegraf_parser = subparsers.add_parser("start-telegraf", help="Start telegraf on testnet nodes")
    start_telegraf_parser.add_argument(
        "--path",
        required=True,
        help="Path to the inputs file"
    )
    start_telegraf_parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompt before dispatching workflow"
    )

    start_uploaders_parser = subparsers.add_parser("start-uploaders", help="Start uploaders on testnet nodes")
    start_uploaders_parser.add_argument(
        "--path",
        required=True,
        help="Path to the inputs file"
    )
    start_uploaders_parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompt before dispatching workflow"
    )

    stop_nodes_parser = subparsers.add_parser("stop-nodes", help="Stop testnet nodes")
    stop_nodes_parser.add_argument(
        "--path",
        required=True,
        help="Path to the inputs file"
    )
    stop_nodes_parser.add_argument(
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

    stop_uploaders_parser = subparsers.add_parser("stop-uploaders", help="Stop uploaders on testnet nodes")
    stop_uploaders_parser.add_argument(
        "--path",
        required=True,
        help="Path to the inputs file"
    )
    stop_uploaders_parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompt before dispatching workflow"
    )

    update_peer_parser = subparsers.add_parser("update-peer", help="Update peer multiaddr on testnet nodes")
    update_peer_parser.add_argument(
        "--path",
        required=True,
        help="Path to the inputs file"
    )
    update_peer_parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompt before dispatching workflow"
    )

    upgrade_antctl_parser = subparsers.add_parser("upgrade-antctl", help="Upgrade antctl version")
    upgrade_antctl_parser.add_argument(
        "--path",
        required=True,
        help="Path to the inputs file"
    )
    upgrade_antctl_parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompt before dispatching workflow"
    )

    upgrade_network_parser = subparsers.add_parser("upgrade-network", help="Upgrade network nodes")
    upgrade_network_parser.add_argument(
        "--path",
        required=True,
        help="Path to the inputs file"
    )
    upgrade_network_parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompt before dispatching workflow"
    )

    upgrade_uploaders_parser = subparsers.add_parser("upgrade-uploaders", help="Upgrade the uploaders to the specified version of autonomi")
    upgrade_uploaders_parser.add_argument(
        "--path",
        required=True,
        help="Path to the inputs file"
    )
    upgrade_uploaders_parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompt before dispatching workflow"
    )

    upscale_network_parser = subparsers.add_parser("upscale-network", help="Upscale an existing network")
    upscale_network_parser.add_argument(
        "--path",
        required=True,
        help="Path to the inputs file"
    )
    upscale_network_parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompt before dispatching workflow"
    )

    reset_to_n_nodes_parser = subparsers.add_parser("reset-to-n-nodes", help="Reset network to run specified number of nodes")
    reset_to_n_nodes_parser.add_argument(
        "--path",
        required=True,
        help="Path to the inputs file"
    )
    reset_to_n_nodes_parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompt before dispatching workflow"
    )

    deployment_print_parser = deployment_subparsers.add_parser(
        "print", 
        help="Print details of a specific deployment"
    )
    deployment_print_parser.add_argument(
        "--id",
        type=int,
        required=True,
        help="ID of the deployment to print"
    )

    args = parser.parse_args()
    
    if args.debug:
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
    
    if args.command == "comparisons":
        if args.comparisons_command == "add-thread":
            cmd.add_comparison_thread(args.id, args.link)
        elif args.comparisons_command == "ls":
            cmd.list_comparisons()
        elif args.comparisons_command == "new":
            cmd.create_comparison_interactive()
        elif args.comparisons_command == "post":
            cmd.post_comparison(args.id)
        elif args.comparisons_command == "print":
            cmd.print_comparison(args.id)
        elif args.comparisons_command == "record-results":
            cmd.record_comparison_results(args.id, args.start, args.end, args.path, args.passed)
        else:
            comparisons_parser.print_help()
            sys.exit(1)
    elif args.command == "deployment":
        if args.deployment_command == "ls":
            cmd.list_deployments(show_details=args.details)
        elif args.deployment_command == "smoke-test":
            cmd.smoke_test_deployment(args.id)
        elif args.deployment_command == "print":
            cmd.print_deployment(args.id)
        else:
            deployment_parser.print_help()
            sys.exit(1)
    elif args.command == "bootstrap-network":
        config = load_yaml_config(args.path)
        cmd.bootstrap_network(config, args.branch, args.force)
    elif args.command == "deposit-funds":
        config = load_yaml_config(args.path)
        cmd.deposit_funds(config, args.branch, args.force)
    elif args.command == "destroy-network":
        config = load_yaml_config(args.path)
        cmd.destroy_network(config, args.branch, args.force)
    elif args.command == "drain-funds":
        config = load_yaml_config(args.path)
        cmd.drain_funds(config, args.branch, args.force)
    elif args.command == "kill-droplets":
        config = load_yaml_config(args.path)
        cmd.kill_droplets(config, args.branch, args.force)
    elif args.command == "launch-legacy-network":
        config = load_yaml_config(args.path)
        cmd.launch_legacy_network(config, "main", args.force)
    elif args.command == "launch-network":
        config = load_yaml_config(args.path)
        cmd.launch_network(config, args.branch, args.force)
    elif args.command == "ls":
        cmd.list_runs(show_details=args.details)
    elif args.command == "network-status":
        config = load_yaml_config(args.path)
        cmd.network_status(config, args.branch, args.force)
    elif args.command == "start-nodes":
        config = load_yaml_config(args.path)
        cmd.start_nodes(config, args.branch, args.force)
    elif args.command == "start-telegraf":
        config = load_yaml_config(args.path)
        cmd.start_telegraf(config, args.branch, args.force)
    elif args.command == "start-uploaders":
        config = load_yaml_config(args.path)
        cmd.start_uploaders(config, args.branch, args.force)
    elif args.command == "stop-nodes":
        config = load_yaml_config(args.path)
        cmd.stop_nodes(config, args.branch, args.force)
    elif args.command == "stop-telegraf":
        config = load_yaml_config(args.path)
        cmd.stop_telegraf(config, args.branch, args.force)
    elif args.command == "stop-uploaders":
        config = load_yaml_config(args.path)
        cmd.stop_uploaders(config, args.branch, args.force)
    elif args.command == "update-peer":
        config = load_yaml_config(args.path)
        cmd.update_peer(config, args.branch, args.force)
    elif args.command == "upgrade-antctl":
        config = load_yaml_config(args.path)
        cmd.upgrade_antctl(config, args.branch, args.force)
    elif args.command == "upgrade-network":
        config = load_yaml_config(args.path)
        cmd.upgrade_network(config, args.branch, args.force)
    elif args.command == "upgrade-uploaders":
        config = load_yaml_config(args.path)
        cmd.upgrade_uploaders(config, args.branch, args.force)
    elif args.command == "upscale-network":
        config = load_yaml_config(args.path)
        cmd.upscale_network(config, args.branch, args.force)
    elif args.command == "reset-to-n-nodes":
        config = load_yaml_config(args.path)
        cmd.reset_to_n_nodes(config, args.branch, args.force)
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()
