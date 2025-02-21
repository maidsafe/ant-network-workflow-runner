import os
import requests
import sys

from typing import Dict

import questionary
from rich import print as rprint

from runner.db import DeploymentRepository, WorkflowRunRepository
from runner.workflows import *

REPO_OWNER = "maidsafe"
REPO_NAME = "sn-testnet-workflows"

BOOTSTRAP_NETWORK_WORKFLOW_ID = 117603859
DEPOSIT_FUNDS_WORKFLOW_ID = 125539747
DESTROY_NETWORK_WORKFLOW_ID = 63357826
DRAIN_FUNDS_WORKFLOW_ID = 125539749
KILL_DROPLETS_WORKFLOW_ID = 128878189
LAUNCH_NETWORK_WORKFLOW_ID = 144945387
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
        "full_cone_private_node_count": 25,
        "symmetric_private_node_count": 25,
        "downloader_count": 0,
        "uploader_count": 1,
        "peer_cache_vm_count": 3,
        "generic_vm_count": 10,
        "full_cone_nat_gateway_vm_count": 1,
        "full_cone_private_vm_count": 1,
        "symmetric_nat_gateway_vm_count": 1,
        "symmetric_private_vm_count": 1,
        "uploader_vm_count": 1,
        "peer_cache_node_vm_size": "s-2vcpu-4gb",
        "generic_node_vm_size": "s-4vcpu-8gb",
        "full_cone_nat_gateway_vm_size": "s-4vcpu-8gb",
        "symmetric_nat_gateway_vm_size": "s-4vcpu-8gb",
        "uploader_vm_size": "s-2vcpu-4gb"
    },
    "staging": {
        "peer_cache_node_count": 5,
        "generic_node_count": 25,
        "full_cone_private_node_count": 25,
        "symmetric_private_node_count": 25,
        "downloader_count": 0,
        "uploader_count": 1,
        "peer_cache_vm_count": 3,
        "generic_vm_count": 39,
        "full_cone_nat_gateway_vm_count": 1,
        "full_cone_private_vm_count": 1,
        "symmetric_nat_gateway_vm_count": 1,
        "symmetric_private_vm_count": 1,
        "uploader_vm_count": 2,
        "peer_cache_node_vm_size": "s-2vcpu-4gb",
        "generic_node_vm_size": "s-2vcpu-4gb",
        "full_cone_nat_gateway_vm_size": "s-2vcpu-4gb",
        "symmetric_nat_gateway_vm_size": "s-2vcpu-4gb",
        "uploader_vm_size": "s-2vcpu-4gb"
    },
    "production": {
        "peer_cache_node_count": 5,
        "generic_node_count": 25,
        "full_cone_private_node_count": 25,
        "symmetric_private_node_count": 25,
        "downloader_count": 0,
        "uploader_count": 1,
        "peer_cache_vm_count": 3,
        "generic_vm_count": 39,
        "full_cone_nat_gateway_vm_count": 1,
        "full_cone_private_vm_count": 1,
        "symmetric_nat_gateway_vm_count": 1,
        "symmetric_private_vm_count": 1,
        "uploader_vm_count": 2,
        "peer_cache_node_vm_size": "s-8vcpu-16gb",
        "generic_node_vm_size": "s-8vcpu-16gb",
        "full_cone_nat_gateway_vm_size": "s-8vcpu-16gb",
        "symmetric_nat_gateway_vm_size": "s-8vcpu-16gb",
        "uploader_vm_size": "s-8vcpu-16gb"
    }
}

def bootstrap_network(config: Dict, branch_name: str, force: bool = False, wait: bool = False) -> None:
    """Bootstrap a new network."""
    _print_workflow_banner()
    
    workflow = BootstrapNetworkWorkflow(
        owner=REPO_OWNER,
        repo=REPO_NAME,
        id=BOOTSTRAP_NETWORK_WORKFLOW_ID,
        personal_access_token=_get_github_token(),
        branch_name=branch_name,
        network_name=config["network-name"],
        peer=config["peer"],
        environment_type=config["environment-type"],
        config=config
    )
    
    try:
        workflow_run_id = workflow.run(force=force, wait=wait)
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

def deposit_funds(config: Dict, branch_name: str, force: bool = False, wait: bool = False) -> None:
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
        personal_access_token=_get_github_token(),
        branch_name=branch_name,
        network_name=config["network-name"],
        provider=config["provider"],
        funding_wallet_secret_key=config.get("funding-wallet-secret-key"),
        gas_to_transfer=config.get("gas-to-transfer"),
        tokens_to_transfer=config.get("tokens-to-transfer"),
        testnet_deploy_args=testnet_deploy_args
    )
    _execute_workflow(workflow, force, wait)

def destroy_network(config: Dict, branch_name: str, force: bool = False, wait: bool = False) -> None:
    """Destroy a network."""
    if not questionary.confirm(
        "Have you drained funds from this network?",
        default=False
    ).ask():
        print("Error: Please drain funds from the network before destroying it")
        sys.exit(1)
    if "network-name" not in config:
        raise KeyError("network-name")
    
    _print_workflow_banner()
    
    testnet_deploy_args = _build_testnet_deploy_args(config)
        
    workflow = DestroyNetworkWorkflow(
        owner=REPO_OWNER,
        repo=REPO_NAME,
        id=DESTROY_NETWORK_WORKFLOW_ID,
        personal_access_token=_get_github_token(),
        branch_name=branch_name,
        network_name=config["network-name"],
        testnet_deploy_args=testnet_deploy_args
    )
    _execute_workflow(workflow, force, wait)

def drain_funds(config: Dict, branch_name: str, force: bool = False, wait: bool = False) -> None:
    """Drain funds from network nodes."""
    if "network-name" not in config:
        raise KeyError("network-name")
    
    _print_workflow_banner()
    
    testnet_deploy_args = _build_testnet_deploy_args(config)
        
    workflow = DrainFundsWorkflow(
        owner=REPO_OWNER,
        repo=REPO_NAME,
        id=DRAIN_FUNDS_WORKFLOW_ID,
        personal_access_token=_get_github_token(),
        branch_name=branch_name,
        network_name=config["network-name"],
        to_address=config.get("to-address"),
        testnet_deploy_args=testnet_deploy_args
    )
    _execute_workflow(workflow, force, wait)

def kill_droplets(config: Dict, branch_name: str, force: bool = False, wait: bool = False) -> None:
    """Kill specified droplets."""
    if "droplet-names" not in config:
        raise KeyError("droplet-names")
    
    _print_workflow_banner()
        
    workflow = KillDropletsWorkflow(
        owner=REPO_OWNER,
        repo=REPO_NAME,
        id=KILL_DROPLETS_WORKFLOW_ID,
        personal_access_token=_get_github_token(),
        branch_name=branch_name,
        network_name=config["network-name"],
        droplet_names=config["droplet-names"]
    )
    _execute_workflow(workflow, force, wait)

def launch_network(config: Dict, branch_name: str, force: bool = False, wait: bool = False) -> None:
    """Launch a new network."""
    _print_workflow_banner()
    
    workflow = LaunchNetworkWorkflow(
        owner=REPO_OWNER,
        repo=REPO_NAME,
        id=LAUNCH_NETWORK_WORKFLOW_ID,
        personal_access_token=_get_github_token(),
        branch_name=branch_name,
        network_name=config["network-name"],
        config=config
    )
    
    try:
        workflow_run_id = workflow.run(force=force, wait=wait)
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

def launch_legacy_network(config: Dict, branch_name: str, force: bool = False, wait: bool = False) -> None:
    """Launch a new legacy network."""
    _print_workflow_banner()
    
    workflow = LaunchLegacyNetworkWorkflow(
        owner=REPO_OWNER,
        repo=REPO_NAME,
        id=LAUNCH_NETWORK_WORKFLOW_ID,
        personal_access_token=_get_github_token(),
        branch_name=branch_name,
        network_name=config["network-name"],
        config=config
    )
    
    try:
        workflow_run_id = workflow.run(force=force, wait=wait)
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

def ls(show_details: bool = False, workflow_name: str = None, network_name: str = None) -> None:
    """List all recorded workflow runs."""

    repo = WorkflowRunRepository()
    runs = repo.list_workflow_runs()
    if not runs:
        print("No workflow runs found.")
        return
    
    if workflow_name:
        runs = [run for run in runs if workflow_name.lower() in run.workflow_name.lower()]
    if network_name:
        runs = [run for run in runs if network_name.lower() in run.network_name.lower()]
    if not runs:
        print("No matching workflow runs found.")
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

def network_status(config: Dict, branch_name: str, force: bool = False, wait: bool = False) -> None:
    """Check status of nodes in a testnet network."""
    if "network-name" not in config:
        raise KeyError("network-name")
    
    _print_workflow_banner()
    
    testnet_deploy_args = _build_testnet_deploy_args(config)
        
    workflow = NetworkStatusWorkflow(
        owner=REPO_OWNER,
        repo=REPO_NAME,
        id=NETWORK_STATUS_WORKFLOW_ID,
        personal_access_token=_get_github_token(),
        branch_name=branch_name,
        network_name=config["network-name"],
        ansible_forks=config.get("ansible-forks"),
        testnet_deploy_args=testnet_deploy_args
    )
    _execute_workflow(workflow, force, wait)


def reset_to_n_nodes(config: Dict, branch_name: str, force: bool = False, wait: bool = False) -> None:
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
        personal_access_token=_get_github_token(),
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
    _execute_workflow(workflow, force, wait)

def stop_nodes(config: Dict, branch_name: str, force: bool = False, wait: bool = False) -> None:
    if "network-name" not in config:
        raise KeyError("network-name")
    
    _print_workflow_banner()
    
    testnet_deploy_args = _build_testnet_deploy_args(config)
        
    workflow = StopNodesWorkflowRun(
        owner=REPO_OWNER,
        repo=REPO_NAME,
        id=STOP_NODES_WORKFLOW_ID,
        personal_access_token=_get_github_token(),
        branch_name=branch_name,
        network_name=config["network-name"],
        ansible_forks=config.get("ansible-forks"),
        custom_inventory=config.get("custom-inventory"),
        delay=config.get("delay"),
        interval=config.get("interval"),
        node_type=NodeType(config["node-type"]) if "node-type" in config else None,
        service_names=config.get("service-names"),
        testnet_deploy_args=testnet_deploy_args
    )
    _execute_workflow(workflow, force, wait)

def start_nodes(config: Dict, branch_name: str, force: bool = False, wait: bool = False) -> None:
    """Start nodes in a testnet network."""
    if "network-name" not in config:
        raise KeyError("network-name")
    
    _print_workflow_banner()
    
    testnet_deploy_args = _build_testnet_deploy_args(config)
        
    workflow = StartNodesWorkflow(
        owner=REPO_OWNER,
        repo=REPO_NAME,
        id=START_NODES_WORKFLOW_ID,
        personal_access_token=_get_github_token(),
        branch_name=branch_name,
        network_name=config["network-name"],
        ansible_forks=config.get("ansible-forks"),
        custom_inventory=config.get("custom-inventory"),
        interval=config.get("interval"),
        node_type=NodeType(config["node-type"]) if "node-type" in config else None,
        testnet_deploy_args=testnet_deploy_args
    )
    _execute_workflow(workflow, force, wait)

def start_uploaders(config: Dict, branch_name: str, force: bool = False, wait: bool = False) -> None:
    """Start uploaders in a testnet network."""
    if "network-name" not in config:
        raise KeyError("network-name")
    
    _print_workflow_banner()
    
    testnet_deploy_args = _build_testnet_deploy_args(config)
        
    workflow = StartUploadersWorkflow(
        owner=REPO_OWNER,
        repo=REPO_NAME,
        id=START_UPLOADERS_WORKFLOW_ID,
        personal_access_token=_get_github_token(),
        branch_name=branch_name,
        network_name=config["network-name"],
        testnet_deploy_args=testnet_deploy_args
    )
    _execute_workflow(workflow, force, wait)

def start_telegraf(config: Dict, branch_name: str, force: bool = False, wait: bool = False) -> None:
    if "network-name" not in config:
        raise KeyError("network-name")
    
    _print_workflow_banner()
    
    testnet_deploy_args = _build_testnet_deploy_args(config)
        
    workflow = StartTelegrafWorkflow(
        owner=REPO_OWNER,
        repo=REPO_NAME,
        id=START_TELEGRAF_WORKFLOW_ID,
        personal_access_token=_get_github_token(),
        branch_name=branch_name,
        network_name=config["network-name"],
        ansible_forks=config.get("ansible-forks"),
        custom_inventory=config.get("custom-inventory"),
        delay=config.get("delay"),
        node_type=NodeType(config["node-type"]) if "node-type" in config else None,
        testnet_deploy_args=testnet_deploy_args
    )
    _execute_workflow(workflow, force, wait)

def stop_telegraf(config: Dict, branch_name: str, force: bool = False, wait: bool = False) -> None:
    if "network-name" not in config:
        raise KeyError("network-name")
    
    _print_workflow_banner()
    
    testnet_deploy_args = _build_testnet_deploy_args(config)
        
    workflow = StopTelegrafWorkflow(
        owner=REPO_OWNER,
        repo=REPO_NAME,
        id=STOP_TELEGRAF_WORKFLOW_ID,
        personal_access_token=_get_github_token(),
        branch_name=branch_name,
        network_name=config["network-name"],
        ansible_forks=config.get("ansible-forks"),
        custom_inventory=config.get("custom-inventory"),
        delay=config.get("delay"),
        node_type=NodeType(config["node-type"]) if "node-type" in config else None,
        testnet_deploy_args=testnet_deploy_args
    )
    _execute_workflow(workflow, force, wait)

def stop_uploaders(config: Dict, branch_name: str, force: bool = False, wait: bool = False) -> None:
    """Stop uploaders in a testnet network."""
    if "network-name" not in config:
        raise KeyError("network-name")
    
    _print_workflow_banner()
    
    testnet_deploy_args = _build_testnet_deploy_args(config)
        
    workflow = StopUploadersWorkflow(
        owner=REPO_OWNER,
        repo=REPO_NAME,
        id=STOP_UPLOADERS_WORKFLOW_ID,
        personal_access_token=_get_github_token(),
        branch_name=branch_name,
        network_name=config["network-name"],
        testnet_deploy_args=testnet_deploy_args
    )
    _execute_workflow(workflow, force, wait)

def upgrade_antctl(config: Dict, branch_name: str, force: bool = False, wait: bool = False) -> None:
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
        personal_access_token=_get_github_token(),
        branch_name=branch_name,
        network_name=config["network-name"],
        version=config["version"],
        custom_inventory=config.get("custom-inventory"),
        node_type=NodeType(config["node-type"]) if "node-type" in config else None,
        testnet_deploy_args=testnet_deploy_args
    )
    _execute_workflow(workflow, force, wait)

def upgrade_network(config: Dict, branch_name: str, force: bool = False, wait: bool = False) -> None:
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
        personal_access_token=_get_github_token(),
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
    _execute_workflow(workflow, force, wait)

def update_peer(config: Dict, branch_name: str, force: bool = False, wait: bool = False) -> None:
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
        personal_access_token=_get_github_token(),
        branch_name=branch_name,
        network_name=config["network-name"],
        peer=config["peer"],
        custom_inventory=config.get("custom-inventory"),
        node_type=NodeType(config["node-type"]) if "node-type" in config else None
    )
    _execute_workflow(workflow, force, wait)

def upgrade_uploaders(config: Dict, branch_name: str, force: bool = False, wait: bool = False) -> None:
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
        personal_access_token=_get_github_token(),
        branch_name=branch_name,
        network_name=config["network-name"],
        version=config["version"],
        testnet_deploy_args=testnet_deploy_args
    )
    _execute_workflow(workflow, force, wait)

def upscale_network(config: Dict, branch_name: str, force: bool = False, wait: bool = False) -> None:
    """Upscale an existing network."""
    if "network-name" not in config:
        raise KeyError("network-name")
    
    _print_workflow_banner()
        
    workflow = UpscaleNetworkWorkflow(
        owner=REPO_OWNER,
        repo=REPO_NAME,
        id=UPSCALE_NETWORK_WORKFLOW_ID,
        personal_access_token=_get_github_token(),
        branch_name=branch_name,
        network_name=config["network-name"],
        config=config
    )
    _execute_workflow(workflow, force, wait)

def _execute_workflow(workflow, force: bool = False, wait: bool = False) -> None:
    """
    Common function to execute a workflow and handle its output and errors.
    
    Args:
        workflow: The workflow instance to execute
        force: If True, skip confirmation prompt
        wait: If True, wait for workflow completion
    """
    try:
        workflow.run(force=force, wait=wait)
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

def _get_github_token() -> str:
    token = os.getenv("WORKFLOW_RUNNER_PAT")
    if not token:
        raise ValueError("WORKFLOW_RUNNER_PAT environment variable is not set")
    return token

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
