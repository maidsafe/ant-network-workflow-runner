import os
import sys
from datetime import datetime
from typing import Dict, Optional, List

import requests
from rich import print as rprint

from runner.db import ComparisonRepository, DeploymentRepository
from runner.models import Deployment
from runner.workflows import *

REPO_OWNER = "maidsafe"
REPO_NAME = "sn-testnet-workflows"
AUTONOMI_REPO_NAME = "autonomi"

BOOTSTRAP_NETWORK_WORKFLOW_ID = 117603859
DEPOSIT_FUNDS_WORKFLOW_ID = 125539747
DESTROY_NETWORK_WORKFLOW_ID = 63357826
DRAIN_FUNDS_WORKFLOW_ID = 125539749
KILL_DROPLETS_WORKFLOW_ID = 128878189
LAUNCH_NETWORK_WORKFLOW_ID = 58844793
NETWORK_STATUS_WORKFLOW_ID = 109501466
RESET_TO_N_NODES_WORKFLOW_ID = 134957069
START_NODES_WORKFLOW_ID = 109583089
START_TELEGRAF_WORKFLOW_ID = 113666375
START_UPLOADERS_WORKFLOW_ID = 116345515
STOP_NODES_WORKFLOW_ID = 126356854
STOP_TELEGRAF_WORKFLOW_ID = 109718824
STOP_UPLOADERS_WORKFLOW_ID = 116345516
UPDATE_PEER_WORKFLOW_ID = 127823614
UPGRADE_ANTCTL_WORKFLOW_ID = 134531916
UPGRADE_NETWORK_WORKFLOW_ID = 109064529
UPGRADE_UPLOADERS_WORKFLOW_ID = 118769505
UPSCALE_NETWORK_WORKFLOW_ID = 105092652

ENVIRONMENT_DEFAULTS = {
    "development": {
        "peer_cache_node_count": 5,
        "generic_node_count": 25,
        "private_node_count": 25,
        "downloader_count": 0,
        "uploader_count": 1,
        "peer_cache_vm_count": 3,
        "generic_vm_count": 10,
        "private_vm_count": 1,
        "uploader_vm_count": 1,
        "peer_cache_node_vm_size": "s-2vcpu-4gb",
        "generic_node_vm_size": "s-4vcpu-8gb",
        "private_node_vm_size": "s-4vcpu-8gb",
        "uploader_vm_size": "s-2vcpu-4gb"
    },
    "staging": {
        "peer_cache_node_count": 5,
        "generic_node_count": 25,
        "private_node_count": 25,
        "downloader_count": 0,
        "uploader_count": 1,
        "peer_cache_vm_count": 3,
        "generic_vm_count": 39,
        "private_vm_count": 1,
        "uploader_vm_count": 2,
        "peer_cache_node_vm_size": "s-2vcpu-4gb",
        "generic_node_vm_size": "s-4vcpu-8gb",
        "private_node_vm_size": "s-4vcpu-8gb",
        "uploader_vm_size": "s-2vcpu-4gb"
    },
    "production": {
        "peer_cache_node_count": 5,
        "generic_node_count": 25,
        "private_node_count": 25,
        "downloader_count": 0,
        "uploader_count": 1,
        "peer_cache_vm_count": 3,
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

    repo = WorkflowRunRepository()
    runs = repo.list_workflow_runs()
    if not runs:
        print("No workflow runs found.")
        return
        
    print("=" * 61)
    print(" " * 18 + "W O R K F L O W   R U N S" + " " * 18)
    print("=" * 61 + "\n")
    
    if show_details:
        for run in runs:
            timestamp = run.triggered_at.strftime("%Y-%m-%d %H:%M:%S")
            
            rprint(f"Workflow: [green]{run.workflow_name}[/green]")
            print(f"Triggered: {timestamp}")
            print(f"Network: {run.network_name}")
            print(f"Branch: {run.branch_name}")
            print(f"URL: https://github.com/{REPO_OWNER}/{REPO_NAME}/actions/runs/{run.run_id}")
            print("Inputs:")
            for key, value in run.inputs.items():
                print(f"  {key}: {value}")
            print("-" * 50)
    else:
        print(f"{'Triggered':<20} {'Workflow':<25} {'Network':<15}")
        print("-" * 60)
        
        for run in runs:
            timestamp = run.triggered_at.strftime("%Y-%m-%d %H:%M:%S")
            rprint(f"{timestamp:<20} [green]{run.workflow_name:<25}[/green] {run.network_name:<15}")
    
    print("\nAll times are in UTC")

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

def upgrade_antctl(config: Dict, branch_name: str, force: bool = False) -> None:
    """Upgrade antctl version."""
    if "network-name" not in config:
        raise KeyError("network-name")
    if "version" not in config:
        raise KeyError("version")
    
    _print_workflow_banner()
    
    testnet_deploy_args = _build_testnet_deploy_args(config)
        
    workflow = UpgradeAntctlWorkflow(
        owner=REPO_OWNER,
        repo=REPO_NAME,
        id=UPGRADE_ANTCTL_WORKFLOW_ID,
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
        repo = DeploymentRepository()
        repo.record_deployment(workflow_run_id, config, defaults)
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
        "peer-cache-node-count",
        "generic-node-count", 
        "private-node-count",
        "downloader-count",
        "uploader-count"
    ]
    
    vm_counts = [
        "peer-cache-vm-count",
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
        ant_version=config.get("ant-version"),
        antnode_version=config.get("antnode-version"),
        antctl_version=config.get("antctl-version"),
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
        
        repo = DeploymentRepository()
        repo.record_deployment(workflow_run_id, config, defaults, is_legacy=True)
        print("Workflow was dispatched with the following inputs:")
        for key, value in workflow.get_workflow_inputs().items():
            print(f"  {key}: {value}")
    except (KeyError, ValueError) as e:
        print(f"Error: {e}")
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"Error: Failed to trigger workflow: {e}")
        sys.exit(1)

def start_uploaders(config: Dict, branch_name: str, force: bool = False) -> None:
    """Start uploaders in a testnet network."""
    if "network-name" not in config:
        raise KeyError("network-name")
    
    _print_workflow_banner()
    
    testnet_deploy_args = _build_testnet_deploy_args(config)
        
    workflow = StartUploadersWorkflow(
        owner=REPO_OWNER,
        repo=REPO_NAME,
        id=START_UPLOADERS_WORKFLOW_ID,
        personal_access_token=get_github_token(),
        branch_name=branch_name,
        network_name=config["network-name"],
        testnet_deploy_args=testnet_deploy_args
    )
    _execute_workflow(workflow, force)

def stop_uploaders(config: Dict, branch_name: str, force: bool = False) -> None:
    """Stop uploaders in a testnet network."""
    if "network-name" not in config:
        raise KeyError("network-name")
    
    _print_workflow_banner()
    
    testnet_deploy_args = _build_testnet_deploy_args(config)
        
    workflow = StopUploadersWorkflow(
        owner=REPO_OWNER,
        repo=REPO_NAME,
        id=STOP_UPLOADERS_WORKFLOW_ID,
        personal_access_token=get_github_token(),
        branch_name=branch_name,
        network_name=config["network-name"],
        testnet_deploy_args=testnet_deploy_args
    )
    _execute_workflow(workflow, force)

def drain_funds(config: Dict, branch_name: str, force: bool = False) -> None:
    """Drain funds from network nodes."""
    if "network-name" not in config:
        raise KeyError("network-name")
    
    _print_workflow_banner()
    
    testnet_deploy_args = _build_testnet_deploy_args(config)
        
    workflow = DrainFundsWorkflow(
        owner=REPO_OWNER,
        repo=REPO_NAME,
        id=DRAIN_FUNDS_WORKFLOW_ID,
        personal_access_token=get_github_token(),
        branch_name=branch_name,
        network_name=config["network-name"],
        to_address=config.get("to-address"),
        testnet_deploy_args=testnet_deploy_args
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

def list_deployments(show_details: bool = False) -> None:
    """List all recorded deployments."""
    try:
        repo = DeploymentRepository()
        deployments = repo.list_deployments()
        if not deployments:
            print("No deployments found.")
            return
            
        print("=" * 61)
        print(" " * 18 + "D E P L O Y M E N T S" + " " * 18)
        print("=" * 61)
        
        if show_details:
            for deployment in deployments:
                timestamp = deployment.triggered_at.strftime("%Y-%m-%d %H:%M:%S")
                rprint(f"Name: [green]{deployment.name}[/green]")
                print(f"ID: {deployment.id}")
                print(f"Deployed: {timestamp}")
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
                total_nodes = deployment.generic_vm_count * deployment.generic_node_count
                if deployment.peer_cache_vm_count and deployment.peer_cache_node_count:
                    total_nodes += deployment.peer_cache_vm_count * deployment.peer_cache_node_count
                if deployment.private_vm_count and deployment.private_node_count:
                    total_nodes += deployment.private_vm_count * deployment.private_node_count
                print(f"Total: {total_nodes}")

                if deployment.uploader_vm_count and deployment.uploader_count and deployment.uploader_vm_size:
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

                print("-" * 61)
        else:
            print(f"{'ID':<5} {'Name':<7} {'Deployed':<20} {'PR#':<15}")
            print("-" * 60)
            
            for deployment in deployments:
                related_pr = f"#{deployment.related_pr}" if deployment.related_pr else "-"
                timestamp = deployment.triggered_at.strftime("%Y-%m-%d %H:%M:%S")
                rprint(f"{deployment.id:<5} [green]{deployment.name:<7}[/green] {timestamp:<20} {related_pr:<15}")
                print(f"  https://github.com/{REPO_OWNER}/{REPO_NAME}/actions/runs/{deployment.run_id}")
                
        print("\nAll times are in UTC")
    except Exception as e:
        print(f"Error: Failed to retrieve deployments: {e}")
        sys.exit(1)

def create_comparison(test_id: int, ref_id: int, ref_version: Optional[str] = None, test_version: Optional[str] = None) -> None:
    """Create a new comparison between two deployments."""
    repo = ComparisonRepository()
    repo.create_comparison(test_id, ref_id, ref_version, test_version)
    print(f"Created comparison between deployments {test_id} and {ref_id}")

def list_comparisons() -> None:
    """List all recorded comparisons."""
    repo = ComparisonRepository()
    comparisons = repo.list_comparisons()
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

def build_comparison_report(comparison_id: int) -> str:
    """Build a detailed report about a specific comparison.
    
    Args:
        comparison_id: ID of the comparison to report on
        
    Returns:
        str: The formatted comparison report
        
    Raises:
        ValueError: If comparison with given ID is not found
    """
    repo = ComparisonRepository()
    comparison = repo.get_by_id(comparison_id)
    if not comparison:
        raise ValueError(f"Comparison with ID {comparison_id} not found")
        
    lines = []
    lines.append("============================")
    lines.append("   *ENVIRONMENT COMPARISON*  ")
    lines.append("============================")
    lines.append("")

    test_title = ""
    if comparison.test_version:
        test_title = f"{comparison.test_version}"
    elif comparison.test_deployment.related_pr:
        pr_title = get_pr_title(comparison.test_deployment.related_pr)
        test_title = f"{pr_title} [#{comparison.test_deployment.related_pr}]"
    elif comparison.test_deployment.branch:
        test_title = f"{comparison.test_deployment.repo_owner}/{comparison.test_deployment.branch}"

    if comparison.thread_link:
        lines.append(f"Slack thread: {comparison.thread_link}")

    lines.append(f"*TEST*: {test_title} [`{comparison.test_deployment.name}`]")
    lines.append(f"*REF*: {comparison.ref_version} [`{comparison.ref_deployment.name}`]")
    lines.append("")

    lines.append(f"`{comparison.test_deployment.name}`:")
    lines.append("```")
    lines.extend(_format_deployment_details(comparison.test_deployment))
    lines.append("```")
    lines.append("")
    lines.append(f"`{comparison.ref_deployment.name}`:")
    lines.append("```")
    lines.extend(_format_deployment_details(comparison.ref_deployment))
    lines.append("```")

    return "\n".join(lines)

def _format_deployment_details(deployment: Deployment) -> List[str]:
    """Format deployment details into a list of strings.
    
    Args:
        deployment: The deployment to format
        
    Returns:
        List[str]: Lines of formatted deployment details
    """
    lines = []
    lines.append(f"Deployed: {deployment.triggered_at.strftime('%Y-%m-%d %H:%M:%S')}")
    
    evm_type_display = {
        "anvil": "Anvil",
        "arbitrum-one": "Arbitrum One",
        "arbitrum-sepolia": "Arbitrum Sepolia", 
        "custom": "Custom"
    }.get(deployment.evm_network_type, deployment.evm_network_type)
    
    lines.append(f"EVM Type: {evm_type_display}")
    lines.append(f"Workflow run: https://github.com/{REPO_OWNER}/{REPO_NAME}/actions/runs/{deployment.run_id}")
    
    if deployment.related_pr:
        lines.append(f"Related PR: #{deployment.related_pr}")
        lines.append(f"Link: https://github.com/{REPO_OWNER}/{AUTONOMI_REPO_NAME}/pull/{deployment.related_pr}")

    if deployment.ant_version:
        lines.append(f"===============")
        lines.append(f"Version Details")
        lines.append(f"===============")
        lines.append(f"Ant: {deployment.ant_version}")
        lines.append(f"Antnode: {deployment.antnode_version}")
        lines.append(f"Antctl: {deployment.antctl_version}")

    if deployment.branch:
        lines.append(f"=====================")
        lines.append(f"Custom Branch Details")
        lines.append(f"=====================")
        lines.append(f"Branch: {deployment.branch}")
        lines.append(f"Repo Owner: {deployment.repo_owner}")
        lines.append(f"Link: https://github.com/{deployment.repo_owner}/{AUTONOMI_REPO_NAME}/tree/{deployment.branch}")
        if deployment.chunk_size:
            lines.append(f"Chunk Size: {deployment.chunk_size}")
        if deployment.antnode_features:
            lines.append(f"Antnode Features: {deployment.antnode_features}")

    lines.append(f"==================")
    lines.append(f"Node Configuration")
    lines.append(f"==================")
    lines.append(f"Peer cache nodes: {deployment.peer_cache_vm_count}x{deployment.peer_cache_node_count} [{deployment.peer_cache_node_vm_size}]")
    lines.append(f"Generic nodes: {deployment.generic_vm_count}x{deployment.generic_node_count} [{deployment.generic_node_vm_size}]")
    lines.append(f"Private nodes: {deployment.private_vm_count}x{deployment.private_node_count} [{deployment.private_node_vm_size}]")
    total_nodes = (deployment.peer_cache_vm_count * deployment.peer_cache_node_count + 
                   deployment.generic_vm_count * deployment.generic_node_count +
                   deployment.private_vm_count * deployment.private_node_count)
    lines.append(f"Total: {total_nodes}")

    lines.append(f"======================")
    lines.append(f"Uploader Configuration")
    lines.append(f"======================")
    lines.append(f"{deployment.uploader_vm_count}x{deployment.uploader_count} [{deployment.uploader_vm_size}]")
    total_uploaders = deployment.uploader_vm_count * deployment.uploader_count
    lines.append(f"Total: {total_uploaders}")

    if deployment.max_log_files or deployment.max_archived_log_files:
        lines.append(f"==================")
        lines.append(f"Misc Configuration")
        lines.append(f"==================")
        if deployment.max_log_files:
            lines.append(f"Max log files: {deployment.max_log_files}")
        if deployment.max_archived_log_files:
            lines.append(f"Max archived log files: {deployment.max_archived_log_files}")
        
    if any([deployment.evm_data_payments_address, 
            deployment.evm_payment_token_address, 
            deployment.evm_rpc_url]):
        lines.append(f"=================")
        lines.append(f"EVM Configuration")
        lines.append(f"=================")
        if deployment.evm_data_payments_address:
            lines.append(f"Data Payments Address: {deployment.evm_data_payments_address}")
        if deployment.evm_payment_token_address:
            lines.append(f"Payment Token Address: {deployment.evm_payment_token_address}")
        if deployment.evm_rpc_url:
            lines.append(f"RPC URL: {deployment.evm_rpc_url}")
            
    return lines

def print_comparison(comparison_id: int) -> None:
    """Print detailed information about a specific comparison."""
    try:
        report = build_comparison_report(comparison_id)
        print(report)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

def post_comparison(comparison_id: int) -> None:
    """Post a comparison report to Slack.
    
    Args:
        comparison_id: ID of the comparison to post
    """
    webhook_url = os.getenv("ANT_RUNNER_COMPARISON_WEBHOOK_URL")
    if not webhook_url:
        print("Error: ANT_RUNNER_COMPARISON_WEBHOOK_URL environment variable is not set")
        sys.exit(1)
        
    try:
        report = build_comparison_report(comparison_id)
        
        print("\nSmoke test for TEST environment:")
        test_results = _get_smoke_test_responses()
        
        print("\nSmoke test for REF environment:")
        ref_results = _get_smoke_test_responses()
        
        smoke_test_report = _build_smoke_test_report(test_results, ref_results)
        
        full_report = f"{report}\n\n{smoke_test_report}"
        
        response = requests.post(
            webhook_url,
            json={"text": full_report},
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        
        print(f"Successfully posted comparison {comparison_id} to Slack")
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"Error posting to Slack: {e}")
        sys.exit(1)

def _get_smoke_test_responses() -> dict:
    """Get user responses for smoke test questions.
    
    Returns:
        dict: Dictionary containing smoke test responses
    """
    import questionary
    
    questions = {
        "peer_cache_available": "Are the peer cache files accessible?",
        "antnode_version": "Is the `antnode` version correct?",
        "antctl_version": "Is the `antctl` version correct?",
        "nodes_running": "Are all nodes running?",
        "wallets_funded": "Are the uploader wallets funded?",
        "ant_version": "Is the `ant` version correct?",
        "uploaders_running": "Are the uploaders running without errors?",
        "dashboard_receiving": "Is the main monitoring dashboard receiving data?",
        "uploader_dashboard_receiving": "Is the uploader monitoring dashboard receiving data?"
    }
    
    responses = {}
    for key, question in questions.items():
        response = questionary.confirm(question).ask()
        responses[key] = response
        
    return responses

def _build_smoke_test_report(test_results: dict, ref_results: dict) -> str:
    """Build smoke test report section.
    
    Args:
        test_results: Dictionary containing TEST environment responses
        ref_results: Dictionary containing REF environment responses
        
    Returns:
        str: Formatted smoke test report
    """
    lines = []
    lines.append("----------------")
    lines.append("  Smoke Test  ")
    lines.append("----------------")
    
    lines.append("`TEST`:")
    lines.extend([
        f"{'✅' if test_results['peer_cache_available'] else '❌'}Peer cache files available",
        f"{'✅' if test_results['antnode_version'] else '❌'}`antnode` version is correct",
        f"{'✅' if test_results['antctl_version'] else '❌'}`antctl` version is correct",
        f"{'✅' if test_results['nodes_running'] else '❌'}All nodes running",
        f"{'✅' if test_results['wallets_funded'] else '❌'}Uploader wallets funded",
        f"{'✅' if test_results['ant_version'] else '❌'}`ant` version is correct",
        f"{'✅' if test_results['uploaders_running'] else '❌'}Uploaders running without errors",
        f"{'✅' if test_results['dashboard_receiving'] else '❌'}Main monitoring dashboard receiving data",
        f"{'✅' if test_results['uploader_dashboard_receiving'] else '❌'}Uploader monitoring dashboard receiving data"
    ])
    
    lines.append("")
    
    lines.append("`REF`:")
    lines.extend([
        f"{'✅' if test_results['peer_cache_available'] else '❌'}Peer cache files available",
        f"{'✅' if ref_results['antnode_version'] else '❌'}`antnode` version is correct",
        f"{'✅' if ref_results['antctl_version'] else '❌'}`antctl` version is correct",
        f"{'✅' if ref_results['nodes_running'] else '❌'}All nodes running",
        f"{'✅' if ref_results['wallets_funded'] else '❌'}Uploader wallets funded",
        f"{'✅' if ref_results['ant_version'] else '❌'}`ant` version is correct",
        f"{'✅' if ref_results['uploaders_running'] else '❌'}Uploaders running without errors",
        f"{'✅' if ref_results['dashboard_receiving'] else '❌'}Main monitoring dashboard receiving data",
        f"{'✅' if test_results['uploader_dashboard_receiving'] else '❌'}Uploader monitoring dashboard receiving data"
    ])
    
    return "\n".join(lines)

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
    repo = ComparisonRepository()
    comparison = repo.get_by_id(comparison_id)
    if not comparison:
        raise ValueError(f"Comparison with ID {comparison_id} not found")
    comparison.thread_link = thread_link
    repo.save(comparison)

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
        
    repo = ComparisonRepository()
    comparison = repo.get_by_id(comparison_id)
    if not comparison:
        raise ValueError(f"Comparison with ID {comparison_id} not found")
    comparison.started_at = datetime.fromisoformat(started_at)
    comparison.ended_at = datetime.fromisoformat(ended_at)
    comparison.report = report_content
    comparison.result_recorded_at = datetime.now(UTC)
    comparison.passed = passed
    repo.save(comparison)

def network_status(config: Dict, branch_name: str, force: bool = False) -> None:
    """Check status of nodes in a testnet network."""
    if "network-name" not in config:
        raise KeyError("network-name")
    
    _print_workflow_banner()
    
    testnet_deploy_args = _build_testnet_deploy_args(config)
        
    workflow = NetworkStatusWorkflow(
        owner=REPO_OWNER,
        repo=REPO_NAME,
        id=NETWORK_STATUS_WORKFLOW_ID,
        personal_access_token=get_github_token(),
        branch_name=branch_name,
        network_name=config["network-name"],
        ansible_forks=config.get("ansible-forks"),
        testnet_deploy_args=testnet_deploy_args
    )
    _execute_workflow(workflow, force)

def bootstrap_network(config: Dict, branch_name: str, force: bool = False) -> None:
    """Bootstrap a new network."""
    _print_workflow_banner()
    
    workflow = BootstrapNetworkWorkflow(
        owner=REPO_OWNER,
        repo=REPO_NAME,
        id=BOOTSTRAP_NETWORK_WORKFLOW_ID,
        personal_access_token=get_github_token(),
        branch_name=branch_name,
        network_name=config["network-name"],
        peer=config["peer"],
        environment_type=config["environment-type"],
        config=config
    )
    
    try:
        workflow_run_id = workflow.run(force=force)
        env_type = config.get("environment-type", "development")
        defaults = ENVIRONMENT_DEFAULTS[env_type]
        repo = DeploymentRepository()
        repo.record_deployment(workflow_run_id, config, defaults, is_bootstrap=True)
        print("Workflow was dispatched with the following inputs:")
        for key, value in workflow.get_workflow_inputs().items():
            print(f"  {key}: {value}")
    except (KeyError, ValueError) as e:
        print(f"Error: {e}")
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"Error: Failed to trigger workflow: {e}")
        sys.exit(1)

def reset_to_n_nodes(config: Dict, branch_name: str, force: bool = False) -> None:
    """Reset network to run specified number of nodes."""
    if "network-name" not in config:
        raise KeyError("network-name")
    if "evm-network-type" not in config:
        raise KeyError("evm-network-type")
    if "node-count" not in config:
        raise KeyError("node-count")
    
    _print_workflow_banner()
    
    testnet_deploy_args = _build_testnet_deploy_args(config)
        
    workflow = ResetToNNodesWorkflow(
        owner=REPO_OWNER,
        repo=REPO_NAME,
        id=RESET_TO_N_NODES_WORKFLOW_ID,
        personal_access_token=get_github_token(),
        branch_name=branch_name,
        network_name=config["network-name"],
        evm_network_type=config["evm-network-type"],
        node_count=str(config["node-count"]),
        custom_inventory=config.get("custom-inventory"),
        forks=config.get("forks"),
        node_type=NodeType(config["node-type"]) if "node-type" in config else None,
        start_interval=config.get("start-interval"),
        stop_interval=config.get("stop-interval"),
        version=config.get("version"),
        testnet_deploy_args=testnet_deploy_args
    )
    _execute_workflow(workflow, force)

def create_comparison_interactive() -> None:
    """Create a new comparison using interactive prompts."""
    import questionary

    description = questionary.text(
        "Description (optional):",
    ).ask()

    ref_id = questionary.text(
        "What is the ID of the reference deployment?",
        validate=lambda text: text.isdigit() and int(text) > 0 or "Please enter a valid deployment ID"
    ).ask()
    ref_id = int(ref_id)

    ref_label = questionary.text(
        "What is the label for the reference environment? (e.g. version number or PR#)",
    ).ask()

    num_tests = questionary.text(
        "How many test environments are in this comparison?",
        default="1",
        validate=lambda text: text.isdigit() and int(text) > 0 or "Please enter a valid number"
    ).ask()
    num_tests = int(num_tests)

    test_envs = []
    for i in range(num_tests):
        print(f"\nTest Environment #{i+1}")
        print("-" * 20)
        
        test_id = questionary.text(
            "What is the ID of this test deployment?",
            validate=lambda text: text.isdigit() and int(text) > 0 or "Please enter a valid deployment ID"
        ).ask()
        test_id = int(test_id)

        test_label = questionary.text(
            "What is the label for this test environment? (e.g. version number or PR#)",
        ).ask()

        test_envs.append((test_id, test_label))


    repo = ComparisonRepository()
    repo.create_comparison(ref_id, test_envs, ref_label, description if description else None)
    print(f"\nComparison created")