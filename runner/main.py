import argparse
import logging
import sys
from typing import Dict

import yaml

from runner import cmd
from runner.cmd import comparisons, deployments, workflows

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

    comparisons_parser = subparsers.add_parser("comparisons", help="Manage deployment comparisons")
    comparisons_subparsers = comparisons_parser.add_subparsers(dest="comparisons_command", help="Available comparison commands")
    
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

    comparisons_subparsers.add_parser("ls", help="List all comparisons")
    comparisons_subparsers.add_parser("new", help="Create a new comparison")
    
    comparisons_print_parser = comparisons_subparsers.add_parser("print", help="Print details of a specific comparison")
    comparisons_print_parser.add_argument(
        "--id",
        type=int,
        required=True,
        help="ID of the comparison to print"
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
    
    deployments_parser = subparsers.add_parser("deployments", help="Manage deployments")
    deployments_subparsers = deployments_parser.add_subparsers(dest="deployments_command", help="Available deployment commands")
    
    deployments_ls_parser = deployments_subparsers.add_parser("ls", help="List all deployments")
    deployments_ls_parser.add_argument(
        "--details",
        action="store_true",
        help="Show detailed information for each deployment"
    )

    deployments_post_parser = deployments_subparsers.add_parser(
        "post", 
        help="Post deployment details to Slack"
    )
    deployments_post_parser.add_argument(
        "--id",
        type=int,
        required=True,
        help="ID of the deployment to post"
    )

    deployments_print_parser = deployments_subparsers.add_parser(
        "print", 
        help="Print details of a specific deployment"
    )
    deployments_print_parser.add_argument(
        "--id",
        type=int,
        required=True,
        help="ID of the deployment to print"
    )

    deployments_smoke_test_parser = deployments_subparsers.add_parser(
        "smoke-test", 
        help="Run a smoke test for a deployment"
    )
    deployments_smoke_test_parser.add_argument(
        "--id",
        type=int,
        required=True,
        help="ID of the deployment to test"
    )

    deployments_upload_report_parser = deployments_subparsers.add_parser(
        "upload-report",
        help="Generate a report for uploads on a deployment used for a test"
    )
    deployments_upload_report_parser.add_argument(
        "--id",
        type=int,
        required=True,
        help="The ID of the deployment"
    )

    workflows_parser = subparsers.add_parser("workflows", help="Manage network workflows")
    workflows_parser.add_argument(
        "--wait",
        action="store_true",
        help="Wait for the workflow run to complete"
    )
    workflows_subparsers = workflows_parser.add_subparsers(dest="workflows_command", help="Available workflow commands")

    bootstrap_network_parser = workflows_subparsers.add_parser("bootstrap-network", help="Bootstrap a new network")
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

    deposit_funds_parser = workflows_subparsers.add_parser("deposit-funds", help="Deposit funds to network nodes")
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

    destroy_network_parser = workflows_subparsers.add_parser("destroy-network", help="Destroy a testnet network")
    destroy_network_parser.add_argument(
        "--path",
        required=True,
        help="Path to the inputs file"
    )
    destroy_network_parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompt before dispatching workflow"
    )

    drain_funds_parser = workflows_subparsers.add_parser("drain-funds", help="Drain funds from network nodes")
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

    kill_droplets_parser = workflows_subparsers.add_parser("kill-droplets", help="Kill specified droplets")
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

    launch_legacy_network_parser = workflows_subparsers.add_parser("launch-legacy-network", help="Launch a new legacy network")
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

    launch_network_parser = workflows_subparsers.add_parser("launch-network", help="Launch a new network")
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

    ls_parser = workflows_subparsers.add_parser("ls", help="List all workflow runs")
    ls_parser.add_argument(
        "--details",
        action="store_true",
        help="Show detailed information for each workflow run"
    )
    ls_parser.add_argument(
        "--name",
        help="Filter workflow runs by workflow name"
    )
    ls_parser.add_argument(
        "--network-name",
        help="Filter workflow runs by network name"
    )

    network_status_parser = workflows_subparsers.add_parser("network-status", help="Check status of testnet nodes")
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

    reset_to_n_nodes_parser = workflows_subparsers.add_parser("reset-to-n-nodes", help="Reset network to run specified number of nodes")
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

    start_nodes_parser = workflows_subparsers.add_parser("start-nodes", help="Start testnet nodes")
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

    start_telegraf_parser = workflows_subparsers.add_parser("start-telegraf", help="Start telegraf on testnet nodes")
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

    start_uploaders_parser = workflows_subparsers.add_parser("start-uploaders", help="Start uploaders on testnet nodes")
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

    stop_nodes_parser = workflows_subparsers.add_parser("stop-nodes", help="Stop testnet nodes")
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

    stop_telegraf_parser = workflows_subparsers.add_parser("stop-telegraf", help="Stop telegraf on testnet nodes")
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

    stop_uploaders_parser = workflows_subparsers.add_parser("stop-uploaders", help="Stop uploaders on testnet nodes")
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

    update_peer_parser = workflows_subparsers.add_parser("update-peer", help="Update peer multiaddr on testnet nodes")
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

    upgrade_antctl_parser = workflows_subparsers.add_parser("upgrade-antctl", help="Upgrade antctl version")
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

    upgrade_network_parser = workflows_subparsers.add_parser("upgrade-network", help="Upgrade network nodes")
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

    upgrade_uploaders_parser = workflows_subparsers.add_parser("upgrade-uploaders", help="Upgrade the uploaders to the specified version of autonomi")
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

    upscale_network_parser = workflows_subparsers.add_parser("upscale-network", help="Upscale an existing network")
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

    args = parser.parse_args()
    
    if args.debug:
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
    
    if args.command == "comparisons":
        if args.comparisons_command == "add-thread":
            comparisons.add_thread(args.id, args.link)
        elif args.comparisons_command == "ls":
            comparisons.ls()
        elif args.comparisons_command == "new":
            comparisons.new()
        elif args.comparisons_command == "post":
            comparisons.post(args.id)
        elif args.comparisons_command == "print":
            comparisons.print_comparison(args.id)
        elif args.comparisons_command == "record-results":
            comparisons.record_results(args.id, args.start, args.end, args.path, args.passed)
        else:
            comparisons_parser.print_help()
            sys.exit(1)
    elif args.command == "deployments":
        if args.deployments_command == "ls":
            deployments.ls(show_details=args.details)
        elif args.deployments_command == "post":
            deployments.post(args.id)
        elif args.deployments_command == "print":
            deployments.print_deployment(args.id)
        elif args.deployments_command == "smoke-test":
            deployments.smoke_test(args.id)
        elif args.deployments_command == "upload-report":
            deployments.upload_report(args.id)
        else:
            deployments_parser.print_help()
            sys.exit(1)
    elif args.command == "workflows":
        if args.workflows_command == "bootstrap-network":
            config = load_yaml_config(args.path)
            workflows.bootstrap_network(config, args.branch, args.force, args.wait)
        elif args.workflows_command == "deposit-funds":
            config = load_yaml_config(args.path)
            workflows.deposit_funds(config, args.branch, args.force, args.wait)
        elif args.workflows_command == "destroy-network":
            config = load_yaml_config(args.path)
            workflows.destroy_network(config, args.branch, args.force, args.wait)
        elif args.workflows_command == "drain-funds":
            config = load_yaml_config(args.path)
            workflows.drain_funds(config, args.branch, args.force, args.wait)
        elif args.workflows_command == "kill-droplets":
            config = load_yaml_config(args.path)
            workflows.kill_droplets(config, args.branch, args.force, args.wait)
        elif args.workflows_command == "launch-legacy-network":
            config = load_yaml_config(args.path)
            workflows.launch_legacy_network(config, "main", args.force, args.wait)
        elif args.workflows_command == "launch-network":
            config = load_yaml_config(args.path)
            workflows.launch_network(config, args.branch, args.force, args.wait)
        elif args.workflows_command == "ls":
            workflows.ls(show_details=args.details, workflow_name=args.name, network_name=args.network_name)
        elif args.workflows_command == "network-status":
            config = load_yaml_config(args.path)
            workflows.network_status(config, args.branch, args.force, args.wait)
        elif args.workflows_command == "start-nodes":
            config = load_yaml_config(args.path)
            workflows.start_nodes(config, args.branch, args.force, args.wait)
        elif args.workflows_command == "start-telegraf":
            config = load_yaml_config(args.path)
            workflows.start_telegraf(config, args.branch, args.force, args.wait)
        elif args.workflows_command == "start-uploaders":
            config = load_yaml_config(args.path)
            workflows.start_uploaders(config, args.branch, args.force, args.wait)
        elif args.workflows_command == "stop-nodes":
            config = load_yaml_config(args.path)
            workflows.stop_nodes(config, args.branch, args.force, args.wait)
        elif args.workflows_command == "stop-telegraf":
            config = load_yaml_config(args.path)
            workflows.stop_telegraf(config, args.branch, args.force, args.wait)
        elif args.workflows_command == "stop-uploaders":
            config = load_yaml_config(args.path)
            workflows.stop_uploaders(config, args.branch, args.force, args.wait)
        elif args.workflows_command == "update-peer":
            config = load_yaml_config(args.path)
            workflows.update_peer(config, args.branch, args.force, args.wait)
        elif args.workflows_command == "upgrade-antctl":
            config = load_yaml_config(args.path)
            workflows.upgrade_antctl(config, args.branch, args.force, args.wait)
        elif args.workflows_command == "upgrade-network":
            config = load_yaml_config(args.path)
            workflows.upgrade_network(config, args.branch, args.force, args.wait)
        elif args.workflows_command == "upgrade-uploaders":
            config = load_yaml_config(args.path)
            workflows.upgrade_uploaders(config, args.branch, args.force, args.wait)
        elif args.workflows_command == "upscale-network":
            config = load_yaml_config(args.path)
            workflows.upscale_network(config, args.branch, args.force, args.wait)
        elif args.workflows_command == "reset-to-n-nodes":
            config = load_yaml_config(args.path)
            workflows.reset_to_n_nodes(config, args.branch, args.force, args.wait)
        else:
            workflows_parser.print_help()
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()
