import json
import sqlite3
import os
import sys
from datetime import datetime
from typing import Dict, Optional

import requests
from rich import print as rprint

from runner.db import (
    create_comparison as db_create_comparison,
    list_comparisons as db_list_comparisons,
    list_deployments as db_list_deployments,
    list_workflow_runs,
    record_deployment,
    validate_comparison_deployment_ids,
    get_comparison,
    update_comparison_thread_link,
    update_comparison_results,
)
from runner.models import Deployment
from runner.workflows import (
    DepositFundsWorkflow,
    DestroyNetworkWorkflow,
    KillDropletsWorkflow,
    LaunchNetworkWorkflow,
    LaunchLegacyNetworkWorkflow,
    NodeType,
    StartNodesWorkflow,
    StartTelegrafWorkflow,
    StopNodesWorkflowRun,
    StopTelegrafWorkflow,
    UpdatePeerWorkflow,
    UpgradeNetworkWorkflow,
    UpgradeNodeManagerWorkflow,
    UpgradeUploadersWorkflow,
    UpscaleNetworkWorkflow,
)

REPO_OWNER = "maidsafe"
REPO_NAME = "sn-testnet-workflows"
AUTONOMI_REPO_NAME = "autonomi"

DEPOSIT_FUNDS_WORKFLOW_ID = 125539747
DESTROY_NETWORK_WORKFLOW_ID = 63357826
KILL_DROPLETS_WORKFLOW_ID = 128878189
LAUNCH_NETWORK_WORKFLOW_ID = 58844793
START_NODES_WORKFLOW_ID = 109583089
START_TELEGRAF_WORKFLOW_ID = 113666375
STOP_NODES_WORKFLOW_ID = 126356854
STOP_TELEGRAF_WORKFLOW_ID = 109718824
UPDATE_PEER_WORKFLOW_ID = 127823614
UPGRADE_NODE_MANAGER_WORKFLOW_ID = 109612531
UPGRADE_NETWORK_WORKFLOW_ID = 109064529
UPGRADE_UPLOADERS_WORKFLOW_ID = 118769505
UPSCALE_NETWORK_WORKFLOW_ID = 105092652

ENVIRONMENT_DEFAULTS = {
    "development": {
        "peer_cache_node_count": 1,
        "generic_node_count": 25,
        "private_node_count": 25,
        "downloader_count": 0,
        "uploader_count": 1,
        "peer_cache_vm_count": 1,
        "generic_vm_count": 10,
        "private_vm_count": 1,
        "uploader_vm_count": 1,
        "peer_cache_node_vm_size": "s-2vcpu-4gb",
        "generic_node_vm_size": "s-4vcpu-8gb",
        "private_node_vm_size": "s-4vcpu-8gb",
        "uploader_vm_size": "s-2vcpu-4gb"
    },
    "staging": {
        "peer_cache_node_count": 1,
        "generic_node_count": 25,
        "private_node_count": 25,
        "downloader_count": 0,
        "uploader_count": 1,
        "peer_cache_vm_count": 2,
        "generic_vm_count": 39,
        "private_vm_count": 1,
        "uploader_vm_count": 2,
        "peer_cache_node_vm_size": "s-2vcpu-4gb",
        "generic_node_vm_size": "s-4vcpu-8gb",
        "private_node_vm_size": "s-4vcpu-8gb",
        "uploader_vm_size": "s-2vcpu-4gb"
    },
    "production": {
        "peer_cache_node_count": 1,
        "generic_node_count": 25,
        "private_node_count": 25,
        "downloader_count": 0,
        "uploader_count": 1,
        "peer_cache_vm_count": 2,
        "generic_vm_count": 39,
        "private_vm_count": 1,
        "uploader_vm_count": 2,
        "peer_cache_node_vm_size": "s-8vcpu-16gb",
        "generic_node_vm_size": "s-8vcpu-16gb",
        "private_node_vm_size": "s-8vcpu-16gb",
        "uploader_vm_size": "s-8vcpu-16gb"
    }
}

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

def upgrade_uploaders(config: Dict, branch_name: str, force: bool = False) -> None:
    """Trigger the upgrade uploaders workflow."""
    if "network-name" not in config:
        raise KeyError("network-name")
    if "version" not in config:
        raise KeyError("version")
    
    _print_workflow_banner()
    
    testnet_deploy_args = _build_testnet_deploy_args(config)
        
    workflow = UpgradeUploadersWorkflow(
        owner=REPO_OWNER,
        repo=REPO_NAME,
        id=UPGRADE_UPLOADERS_WORKFLOW_ID,
        personal_access_token=get_github_token(),
        branch_name=branch_name,
        network_name=config["network-name"],
        version=config["version"],
        testnet_deploy_args=testnet_deploy_args
    )
    _execute_workflow(workflow, force)

def launch_network(config: Dict, branch_name: str, force: bool = False) -> None:
    """Launch a new network."""
    _print_workflow_banner()
    
    workflow = LaunchNetworkWorkflow(
        owner=REPO_OWNER,
        repo=REPO_NAME,
        id=LAUNCH_NETWORK_WORKFLOW_ID,
        personal_access_token=get_github_token(),
        branch_name=branch_name,
        network_name=config["network-name"],
        config=config
    )
    
    try:
        workflow_run_id = workflow.run(force=force)
        env_type = config.get("environment-type", "development")
        defaults = ENVIRONMENT_DEFAULTS[env_type]
        record_deployment(workflow_run_id, config, defaults)
        print("Workflow was dispatched with the following inputs:")
        for key, value in workflow.get_workflow_inputs().items():
            print(f"  {key}: {value}")
    except (KeyError, ValueError) as e:
        print(f"Error: {e}")
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"Error: Failed to trigger workflow: {e}")
        sys.exit(1)

def kill_droplets(config: Dict, branch_name: str, force: bool = False) -> None:
    """Kill specified droplets."""
    if "droplet-names" not in config:
        raise KeyError("droplet-names")
    
    _print_workflow_banner()
        
    workflow = KillDropletsWorkflow(
        owner=REPO_OWNER,
        repo=REPO_NAME,
        id=KILL_DROPLETS_WORKFLOW_ID,
        personal_access_token=get_github_token(),
        branch_name=branch_name,
        network_name=config["network-name"],
        droplet_names=config["droplet-names"]
    )
    _execute_workflow(workflow, force)

def upscale_network(config: Dict, branch_name: str, force: bool = False) -> None:
    """Upscale an existing network."""
    if "network-name" not in config:
        raise KeyError("network-name")
    
    node_counts = [
        "bootstrap-node-count",
        "generic-node-count", 
        "private-node-count",
        "downloader-count",
        "uploader-count"
    ]
    
    vm_counts = [
        "bootstrap-vm-count",
        "generic-vm-count",
        "private-vm-count",
        "uploader-vm-count"
    ]
    
    node_count_values = [str(config.get(count, 0)) for count in node_counts]
    vm_count_values = [str(config.get(count, 0)) for count in vm_counts]
    desired_counts = f"({', '.join(node_count_values)}), ({', '.join(vm_count_values)})"
    
    _print_workflow_banner()
    
    testnet_deploy_repo_ref = None
    if "testnet-deploy-branch" in config and "testnet-deploy-repo-owner" in config:
        testnet_deploy_repo_ref = f"{config['testnet-deploy-repo-owner']}/{config['testnet-deploy-branch']}"
    elif bool(config.get("testnet-deploy-branch")) != bool(config.get("testnet-deploy-repo-owner")):
        raise ValueError("testnet-deploy-branch and testnet-deploy-repo-owner must be used together")
        
    workflow = UpscaleNetworkWorkflow(
        owner=REPO_OWNER,
        repo=REPO_NAME,
        id=UPSCALE_NETWORK_WORKFLOW_ID,
        personal_access_token=get_github_token(),
        branch_name=branch_name,
        network_name=config["network-name"],
        desired_counts=desired_counts,
        autonomi_version=config.get("autonomi-version"),
        safenode_version=config.get("safenode-version"),
        safenode_manager_version=config.get("safenode-manager-version"),
        infra_only=config.get("infra-only"),
        interval=config.get("interval"),
        plan=config.get("plan"),
        testnet_deploy_repo_ref=testnet_deploy_repo_ref
    )
    _execute_workflow(workflow, force)

def deposit_funds(config: Dict, branch_name: str, force: bool = False) -> None:
    """Deposit funds to network nodes."""
    if "network-name" not in config:
        raise KeyError("network-name")
    if "provider" not in config:
        raise KeyError("provider")
    
    _print_workflow_banner()
    
    testnet_deploy_args = _build_testnet_deploy_args(config)
        
    workflow = DepositFundsWorkflow(
        owner=REPO_OWNER,
        repo=REPO_NAME,
        id=DEPOSIT_FUNDS_WORKFLOW_ID,
        personal_access_token=get_github_token(),
        branch_name=branch_name,
        network_name=config["network-name"],
        provider=config["provider"],
        funding_wallet_secret_key=config.get("funding-wallet-secret-key"),
        gas_to_transfer=config.get("gas-to-transfer"),
        tokens_to_transfer=config.get("tokens-to-transfer"),
        testnet_deploy_args=testnet_deploy_args
    )
    _execute_workflow(workflow, force)

def start_nodes(config: Dict, branch_name: str, force: bool = False) -> None:
    """Start nodes in a testnet network."""
    if "network-name" not in config:
        raise KeyError("network-name")
    
    _print_workflow_banner()
    
    testnet_deploy_args = _build_testnet_deploy_args(config)
        
    workflow = StartNodesWorkflow(
        owner=REPO_OWNER,
        repo=REPO_NAME,
        id=START_NODES_WORKFLOW_ID,
        personal_access_token=get_github_token(),
        branch_name=branch_name,
        network_name=config["network-name"],
        ansible_forks=config.get("ansible-forks"),
        custom_inventory=config.get("custom-inventory"),
        interval=config.get("interval"),
        node_type=NodeType(config["node-type"]) if "node-type" in config else None,
        testnet_deploy_args=testnet_deploy_args
    )
    _execute_workflow(workflow, force)

def launch_legacy_network(config: Dict, branch_name: str, force: bool = False) -> None:
    """Launch a new legacy network."""
    _print_workflow_banner()
    
    workflow = LaunchLegacyNetworkWorkflow(
        owner=REPO_OWNER,
        repo=REPO_NAME,
        id=LAUNCH_NETWORK_WORKFLOW_ID,
        personal_access_token=get_github_token(),
        branch_name=branch_name,
        network_name=config["network-name"],
        config=config
    )
    
    try:
        workflow_run_id = workflow.run(force=force)
        env_type = config.get("environment-type", "development")
        defaults = ENVIRONMENT_DEFAULTS[env_type]
        
        record_deployment(workflow_run_id, config, defaults, is_legacy=True)
        print("Workflow was dispatched with the following inputs:")
        for key, value in workflow.get_workflow_inputs().items():
            print(f"  {key}: {value}")
    except (KeyError, ValueError) as e:
        print(f"Error: {e}")
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"Error: Failed to trigger workflow: {e}")
        sys.exit(1)

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

def list_deployments(show_details: bool = False) -> None:
    """List all recorded deployments."""
    try:
        deployments = db_list_deployments()
        if not deployments:
            print("No deployments found.")
            return
        
        print("=" * 61)
        print(" " * 18 + "D E P L O Y M E N T S" + " " * 18)
        print("=" * 61)
        
        if show_details:
            for deployment in deployments:
                (id, _, name, ant_version, antnode_version, antctl_version,
                 branch, repo_owner, chunk_size, antnode_features, peer_cache_node_count,
                 generic_node_count, private_node_count, _, uploader_count,
                 peer_cache_vm_count, generic_vm_count, private_vm_count, uploader_vm_count,
                 peer_cache_node_vm_size, generic_node_vm_size, private_node_vm_size,
                 uploader_vm_size, evm_network_type, _, max_log_files,
                 max_archived_log_files, evm_data_payments_address, evm_payment_token_address,
                 evm_rpc_url, related_pr, triggered_at, run_id) = deployment
                
                timestamp = datetime.fromisoformat(triggered_at).strftime("%Y-%m-%d %H:%M:%S")
                rprint(f"Name: [green]{name}[/green]")
                print(f"ID: {id}")
                print(f"Deployed: {timestamp}")
                evm_type_display = {
                    "anvil": "Anvil",
                    "arbitrum-one": "Arbitrum One",
                    "arbitrum-sepolia": "Arbitrum Sepolia", 
                    "custom": "Custom"
                }.get(evm_network_type, evm_network_type)
                print(f"EVM Type: {evm_type_display}")
                print(f"Workflow run: https://github.com/{REPO_OWNER}/{REPO_NAME}/actions/runs/{run_id}")
                if related_pr:
                    print(f"Related PR: #{related_pr}")
                    print(f"Link: https://github.com/{REPO_OWNER}/{AUTONOMI_REPO_NAME}/pull/{related_pr}")

                if ant_version:
                    print(f"===============")
                    print(f"Version Details")
                    print(f"===============")
                    print(f"Ant: {ant_version}")
                    print(f"Antnode: {antnode_version}")
                    print(f"Antctl: {antctl_version}")

                if branch:
                    print(f"=====================")
                    print(f"Custom Branch Details")
                    print(f"=====================")
                    print(f"Branch: {branch}")
                    print(f"Repo Owner: {repo_owner}")
                    print(f"Link: https://github.com/{repo_owner}/{AUTONOMI_REPO_NAME}/tree/{branch}")
                    if chunk_size:
                        print(f"Chunk Size: {chunk_size}")
                    if antnode_features:
                        print(f"Antnode Features: {antnode_features}")

                print(f"==================")
                print(f"Node Configuration")
                print(f"==================")
                print(f"Peer cache nodes: {peer_cache_vm_count}x{peer_cache_node_count} [{peer_cache_node_vm_size}]")
                print(f"Generic nodes: {generic_vm_count}x{generic_node_count} [{generic_node_vm_size}]")
                print(f"Private nodes: {private_vm_count}x{private_node_count} [{private_node_vm_size}]")
                total_nodes = (peer_cache_vm_count * peer_cache_node_count + 
                               generic_vm_count * generic_node_count +
                               private_vm_count * private_node_count)
                print(f"Total: {total_nodes}")

                print(f"======================")
                print(f"Uploader Configuration")
                print(f"======================")
                print(f"{uploader_vm_count}x{uploader_count} [{uploader_vm_size}]")
                total_uploaders = uploader_vm_count * uploader_count
                print(f"Total: {total_uploaders}")

                if max_log_files or max_archived_log_files:
                    print(f"==================")
                    print(f"Misc Configuration")
                    print(f"==================")
                    if max_log_files:
                        print(f"Max log files: {max_log_files}")
                    if max_archived_log_files:
                        print(f"Max archived log files: {max_archived_log_files}")
                    
                if any([evm_data_payments_address, evm_payment_token_address, evm_rpc_url]):
                    print(f"=================")
                    print(f"EVM Configuration")
                    print(f"=================")
                    if evm_data_payments_address:
                        print(f"Data Payments Address: {evm_data_payments_address}")
                    if evm_payment_token_address:
                        print(f"Payment Token Address: {evm_payment_token_address}")
                    if evm_rpc_url:
                        print(f"RPC URL: {evm_rpc_url}")

                print("-" * 61)
        else:
            print(f"{'ID':<5} {'Name':<7} {'Deployed':<20} {'PR#':<15}")
            print("-" * 61)
            
            for deployment in deployments:
                id = deployment[0]
                name = deployment[2]
                triggered_at = deployment[-2]
                run_id = deployment[-1]
                related_pr = deployment[-3]
                if related_pr:
                    related_pr = f"#{related_pr}"
                else:
                    related_pr = "-"
                timestamp = datetime.fromisoformat(triggered_at).strftime("%Y-%m-%d %H:%M:%S")
                rprint(f"{id:<5} [green]{name:<7}[/green] {timestamp:<20} {related_pr:<15}")
                print(f"  https://github.com/{REPO_OWNER}/{REPO_NAME}/actions/runs/{run_id}")
    except sqlite3.Error as e:
        print(f"Error: Failed to retrieve deployments: {e}")
        sys.exit(1)

def create_comparison(test_id: int, ref_id: int, ref_version: Optional[str] = None, test_version: Optional[str] = None) -> None:
    """Create a new comparison between two deployments."""
    try:
        validate_comparison_deployment_ids(test_id, ref_id)
        db_create_comparison(test_id, ref_id, ref_version, test_version)
        print(f"Created comparison between deployments {test_id} and {ref_id}")
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except sqlite3.Error as e:
        print(f"Error: Failed to create comparison: {e}")
        sys.exit(1)

def list_comparisons() -> None:
    """List all recorded comparisons."""
    try:
        comparisons = db_list_comparisons()
        if not comparisons:
            print("No comparisons found.")
            return
            
        print("=" * 100)
        print(" " * 35 + "C O M P A R I S O N S" + " " * 35)
        print("=" * 100)
        
        print(f"{'ID':<5} {'TEST':<15} {'REF':<15} {'Created':<20} {'Results':<20} {'Pass':<5}")
        print("-" * 100)
        
        for comparison in comparisons:
            created_at = comparison.created_at.strftime("%Y-%m-%d %H:%M:%S")
            results_at = comparison.result_recorded_at.strftime("%Y-%m-%d %H:%M:%S") if comparison.result_recorded_at else "-"
            
            if comparison.passed is None:
                pass_mark = "-"
            elif comparison.passed:
                pass_mark = f"[green]✓[/green]"
            else:
                pass_mark = f"[red]✗[/red]"
            rprint(f"{comparison.id:<5} {comparison.test_name:<15} {comparison.ref_name:<15} {created_at:<20} {results_at:<20} {pass_mark:<12}")
            
        print("\nAll times are in UTC")
    except sqlite3.Error as e:
        print(f"Error: Failed to retrieve comparisons: {e}")
        sys.exit(1)

def print_deployment_for_comparison(deployment: Deployment) -> None:
    print(f"Deployed: {deployment.triggered_at.strftime('%Y-%m-%d %H:%M:%S')}")
    evm_type_display = {
        "anvil": "Anvil",
        "arbitrum-one": "Arbitrum One",
        "arbitrum-sepolia": "Arbitrum Sepolia", 
        "custom": "Custom"
    }.get(deployment.evm_network_type, deployment.evm_network_type)
    print(f"EVM Type: {evm_type_display}")
    print(f"Workflow run: https://github.com/{REPO_OWNER}/{REPO_NAME}/actions/runs/{deployment.run_id}")
    if deployment.related_pr:
        print(f"Related PR: #{deployment.related_pr}")
        print(f"Link: https://github.com/{REPO_OWNER}/{AUTONOMI_REPO_NAME}/pull/{deployment.related_pr}")

    if deployment.ant_version:
        print(f"===============")
        print(f"Version Details")
        print(f"===============")
        print(f"Ant: {deployment.ant_version}")
        print(f"Antnode: {deployment.antnode_version}")
        print(f"Antctl: {deployment.antctl_version}")

    if deployment.branch:
        print(f"=====================")
        print(f"Custom Branch Details")
        print(f"=====================")
        print(f"Branch: {deployment.branch}")
        print(f"Repo Owner: {deployment.repo_owner}")
        print(f"Link: https://github.com/{deployment.repo_owner}/{AUTONOMI_REPO_NAME}/tree/{deployment.branch}")
        if deployment.chunk_size:
            print(f"Chunk Size: {deployment.chunk_size}")
        if deployment.antnode_features:
            print(f"Antnode Features: {deployment.antnode_features}")

    print(f"==================")
    print(f"Node Configuration")
    print(f"==================")
    print(f"Peer cache nodes: {deployment.peer_cache_vm_count}x{deployment.peer_cache_node_count} [{deployment.peer_cache_node_vm_size}]")
    print(f"Generic nodes: {deployment.generic_vm_count}x{deployment.generic_node_count} [{deployment.generic_node_vm_size}]")
    print(f"Private nodes: {deployment.private_vm_count}x{deployment.private_node_count} [{deployment.private_node_vm_size}]")
    total_nodes = (deployment.peer_cache_vm_count * deployment.peer_cache_node_count + 
                   deployment.generic_vm_count * deployment.generic_node_count +
                   deployment.private_vm_count * deployment.private_node_count)
    print(f"Total: {total_nodes}")

    print(f"======================")
    print(f"Uploader Configuration")
    print(f"======================")
    print(f"{deployment.uploader_vm_count}x{deployment.uploader_count} [{deployment.uploader_vm_size}]")
    total_uploaders = deployment.uploader_vm_count * deployment.uploader_count
    print(f"Total: {total_uploaders}")


    if deployment.max_log_files or deployment.max_archived_log_files:
        print(f"==================")
        print(f"Misc Configuration")
        print(f"==================")
        if deployment.max_log_files:
            print(f"Max log files: {deployment.max_log_files}")
        if deployment.max_archived_log_files:
            print(f"Max archived log files: {deployment.max_archived_log_files}")
        
    if any([deployment.evm_data_payments_address, 
            deployment.evm_payment_token_address, 
            deployment.evm_rpc_url]):
        print(f"=================")
        print(f"EVM Configuration")
        print(f"=================")
        if deployment.evm_data_payments_address:
            print(f"Data Payments Address: {deployment.evm_data_payments_address}")
        if deployment.evm_payment_token_address:
            print(f"Payment Token Address: {deployment.evm_payment_token_address}")
        if deployment.evm_rpc_url:
            print(f"RPC URL: {deployment.evm_rpc_url}")

def print_comparison(comparison_id: int) -> None:
    """Print detailed information about a specific comparison."""
    comparison = get_comparison(comparison_id)
    if not comparison:
        print(f"Error: Comparison with ID {comparison_id} not found")
        return
        
    print("========================")
    print("*ENVIRONMENT COMPARISON*")
    print("========================")

    test_title = ""
    if comparison.test_deployment.related_pr:
        pr_title = get_pr_title(comparison.test_deployment.related_pr)
        test_title = f"{pr_title} [#{comparison.test_deployment.related_pr}]"
    elif comparison.test_deployment.branch:
        test_title = f"{comparison.test_deployment.repo_owner}/{comparison.test_deployment.branch}"

    print()
    if comparison.thread_link:
        print(f"Slack thread: {comparison.thread_link}")

    print(f"*TEST*: {test_title} [`{comparison.test_deployment.name}`]")
    print(f"*REF*: {comparison.ref_version} [`{comparison.ref_deployment.name}`]")
    print()

    print(f"`{comparison.test_deployment.name}`:")
    print_deployment_for_comparison(comparison.test_deployment)
    print()
    print(f"`{comparison.ref_deployment.name}`:")
    print_deployment_for_comparison(comparison.ref_deployment)

def get_pr_title(pr_number: int) -> str:
    """
    Fetch PR title from GitHub API.
    
    Args:
        pr_number: The PR number to fetch the title for
        
    Returns:
        str: The PR title
        
    Raises:
        RuntimeError: If the PR title cannot be obtained
    """
    url = f"https://api.github.com/repos/maidsafe/autonomi/pulls/{pr_number}"
    headers = {"Accept": "application/vnd.github.v3+json"}
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()["title"]
    except (requests.RequestException, KeyError) as e:
        raise RuntimeError(f"Failed to get PR title for PR #{pr_number}: {str(e)}")

def add_comparison_thread(comparison_id: int, thread_link: str) -> None:
    """Add or update the thread link for a comparison.
    
    Args:
        comparison_id: ID of the comparison to update
        thread_link: URL of the thread where the comparison was posted
    """
    try:
        update_comparison_thread_link(comparison_id, thread_link)
        print(f"Updated thread link for comparison {comparison_id}")
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except sqlite3.Error as e:
        print(f"Error: Failed to update comparison: {e}")
        sys.exit(1)

def record_comparison_results(comparison_id: int, started_at: str, ended_at: str, report_path: str, passed: bool) -> None:
    """Record results for a comparison.
    
    Args:
        comparison_id: ID of the comparison to update
        started_at: Timestamp string for when the comparison started
        ended_at: Timestamp string for when the comparison ended
        report_path: Path to the HTML report file
        passed: Boolean indicating if the comparison passed
        failed: Boolean indicating if the comparison failed
    
    Raises:
        ValueError: If both passed and failed are True, or if both are False
    """
    try:
        try:
            datetime.fromisoformat(started_at)
            datetime.fromisoformat(ended_at)
        except ValueError:
            print("Error: Timestamps must be in ISO format (YYYY-MM-DDTHH:MM:SS)")
            sys.exit(1)
            
        try:
            with open(report_path, 'r', encoding='utf-8') as f:
                report_content = f.read()
        except FileNotFoundError:
            print(f"Error: Report file not found at {report_path}")
            sys.exit(1)
        except IOError as e:
            print(f"Error: Failed to read report file: {e}")
            sys.exit(1)
            
        update_comparison_results(comparison_id, started_at, ended_at, report_content, passed)
        result = "passed" if passed else "failed"
        print(f"Updated results for comparison {comparison_id} - {result}")
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except sqlite3.Error as e:
        print(f"Error: Failed to update comparison: {e}")
        sys.exit(1)