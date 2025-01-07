import os
import requests
import sys

import questionary
from rich import print as rprint
from typing import List

from runner.db import DeploymentRepository
from runner.models import Deployment

REPO_OWNER = "maidsafe"
REPO_NAME = "sn-testnet-workflows"
AUTONOMI_REPO_NAME = "autonomi"

def ls(show_details: bool = False) -> None:
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

def post(deployment_id: int) -> None:
    """Post deployment information to Slack.
    
    Args:
        deployment_id: ID of the deployment to post
    """
    webhook_url = os.getenv("ANT_RUNNER_COMPARISON_WEBHOOK_URL")
    if not webhook_url:
        print("Error: ANT_RUNNER_COMPARISON_WEBHOOK_URL environment variable is not set")
        sys.exit(1)
        
    try:
        repo = DeploymentRepository()
        deployment = repo.get_by_id(deployment_id)
        if not deployment:
            raise ValueError(f"Deployment with ID {deployment_id} not found")

        report = _build_deployment_and_smoke_test_report(deployment)
        
        response = requests.post(
            webhook_url,
            json={"text": report},
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        print(f"Posted deployment report to Slack")
    except requests.exceptions.RequestException as e:
        print(f"Error posting to Slack: {e}")
        sys.exit(1)

def print(deployment_id: int) -> None:
    """Print detailed information about a specific deployment.
    
    Args:
        deployment_id: ID of the deployment to print
    """
    repo = DeploymentRepository()
    deployment = repo.get_by_id(deployment_id)
    if not deployment:
        print(f"Error: Deployment with ID {deployment_id} not found")
        sys.exit(1)
        
    report = _build_deployment_and_smoke_test_report(deployment)
    print(report)

def smoke_test(deployment_id: int) -> None:
    """Run a smoke test for a deployment.
    
    Args:
        deployment_id: ID of the deployment to test
    """
    repo = DeploymentRepository()
    deployment = repo.get_by_id(deployment_id)
    if not deployment:
        print(f"Error: Deployment with ID {deployment_id} not found")
        sys.exit(1)

    print(f"\nSmoke test for {deployment.name}")
    print("-" * 40)

    questions = [
        "Are all nodes running?",
        "Is the main dashboard receiving data?",
        "Do nodes on generic hosts have open connections and connected peers?",
        "Do nodes on peer cache hosts have open connections and connected peers?",
        "Do private nodes have open connections and connected peers?",
        "Is ELK receiving logs?",
        "Is `antctl` on the correct version?",
        "Is `antnode` on the correct version?",
        "Are the correct reserved IPs allocated?",
        "Are the bootstrap cache files available?",
        "Is the uploader dashboard receiving data?",
        "Do uploader wallets have funds?",
        "Is `ant` on the correct version?",
        "Do the uploaders have no errors?"
    ]

    results = {}
    for question in questions:
        answer = questionary.select(
            question,
            choices=["Yes", "No", "N/A"]
        ).ask()
        
        if answer is None:
            print("\nSmoke test cancelled.")
            return
            
        results[question] = answer

    repo.record_smoke_test_result(deployment_id, results)
    print("\nRecorded results")

def _build_deployment_and_smoke_test_report(deployment: Deployment) -> str:
    """Build a detailed report about a specific deployment.
    
    Args:
        deployment: The deployment to format
        
    Returns:
        str: The formatted deployment report
    """
    lines = []
    lines.append(f"*{deployment.name}*")
    
    lines.append("```")
    lines.extend(_build_deployment_report(deployment))
    lines.append("```")
        
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("*SMOKE TEST RESULTS*")
    
    repo = DeploymentRepository()
    results = repo.get_smoke_test_result(deployment.id)
    if not results:
        lines.append("No smoke test results recorded")
    else:
        for question, answer in results.results.items():
            status = {
                "Yes": "✅ ",
                "No": "❌ ",
                "N/A": "N/A"
            }.get(answer, "?")
            lines.append(f"{status}  {question}")
    return "\n".join(lines)

def _build_deployment_report(deployment: Deployment) -> List[str]:
    """Build a detailed report about a specific deployment.
    
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