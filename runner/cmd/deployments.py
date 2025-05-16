import os
import requests
import sys
from datetime import datetime

import questionary
from rich import print as rprint

from runner.db import NetworkDeploymentRepository
from runner.models import NetworkDeployment
from runner.reporting import build_deployment_report
from runner.cmd.workflows import launch_network, start_uploaders, start_downloaders

REPO_OWNER = "maidsafe"
REPO_NAME = "sn-testnet-workflows"
AUTONOMI_REPO_NAME = "autonomi"

def dev(network_name: str) -> None:
    """Launch a development network with preset configuration.
    
    Args:
        network_name: Name of the development environment (e.g. DEV-01)
    """
    if not network_name.startswith("DEV-"):
        print("Error: Network name must start with 'DEV-'")
        sys.exit(1)
    
    config = {
        "description": f"Quick development network for experimentation",
        "environment-type": "development",
        "evm-data-payments-address": "0x7f0842a78f7d4085d975ba91d630d680f91b1295",
        "evm-rpc-url": "https://sepolia-rollup.arbitrum.io/rpc",
        "evm-network-type": "custom",
        "evm-payment-token-address": "0x4bc1ace0e66170375462cb4e6af42ad4d5ec689c",
        "initial-gas": "100000000000000000",  # 0.1 ETH
        "initial-tokens": "1000000000000000000",  # 1 token
        "interval": 5000,
        "max-archived-log-files": 1,
        "max-log-files": 1,
        "network-id": 10,
        "network-name": network_name,
        "region": "lon1",
        "rewards-address": "0x03B770D9cD32077cC0bF330c13C114a87643B124"
    }
    
    launch_network(config, "main", force=False, wait=False)

def ls(show_details: bool = False) -> None:
    """List all recorded deployments."""
    try:
        repo = NetworkDeploymentRepository()
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
                if deployment.description:
                    print(f"Description: {deployment.description}")
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
                print(f"Full cone private nodes: {deployment.full_cone_private_vm_count}x{deployment.full_cone_private_node_count} [{deployment.generic_node_vm_size}]")
                print(f"Symmetric private nodes: {deployment.symmetric_private_vm_count}x{deployment.symmetric_private_node_count} [{deployment.generic_node_vm_size}]")
                total_nodes = deployment.generic_vm_count * deployment.generic_node_count
                if deployment.peer_cache_vm_count and deployment.peer_cache_node_count:
                    total_nodes += deployment.peer_cache_vm_count * deployment.peer_cache_node_count
                if deployment.full_cone_private_vm_count and deployment.full_cone_private_node_count:
                    total_nodes += deployment.full_cone_private_vm_count * deployment.full_cone_private_node_count
                if deployment.symmetric_private_vm_count and deployment.symmetric_private_node_count:
                    total_nodes += deployment.symmetric_private_vm_count * deployment.symmetric_private_node_count
                print(f"Total: {total_nodes}")

                if deployment.client_vm_count and deployment.uploader_count and deployment.client_vm_size:
                    print(f"====================")
                    print(f"Client Configuration")
                    print(f"====================")
                    print(f"{deployment.client_vm_count}x{deployment.uploader_count} [{deployment.client_vm_size}]")
                    total_uploaders = deployment.client_vm_count * deployment.uploader_count
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
            print(f"{'ID':<5} {'Name':<7} {'Deployed':<20} {'PR#':<15} {'Smoke Test':<10}")
            print("-" * 70)
            
            for deployment in deployments:
                related_pr = f"#{deployment.related_pr}" if deployment.related_pr else "-"
                timestamp = deployment.triggered_at.strftime("%Y-%m-%d %H:%M:%S")
                
                smoke_test = repo.get_smoke_test_result(deployment.id)
                if not smoke_test:
                    smoke_status = "-"
                else:
                    has_failures = any(answer == "No" for answer in smoke_test.results.values())
                    smoke_status = "[red]✗[/red]" if has_failures else "[green]✓[/green]"
                
                rprint(f"{deployment.id:<5} [green]{deployment.name:<7}[/green] {timestamp:<20} {related_pr:<15} {smoke_status:<10}")
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
        repo = NetworkDeploymentRepository()
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

def print_deployment(deployment_id: int) -> None:
    """Print detailed information about a specific deployment.
    
    Args:
        deployment_id: ID of the deployment to print
    """
    repo = NetworkDeploymentRepository()
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
    repo = NetworkDeploymentRepository()
    deployment = repo.get_by_id(deployment_id)
    if not deployment:
        print(f"Error: Deployment with ID {deployment_id} not found")
        sys.exit(1)

    print(f"\nSmoke test for {deployment.name}")
    print("-" * 40)

    if deployment.ant_version:
        print(f"Versions:")
        print(f"  ant: {deployment.ant_version}")
        print(f"  antnode: {deployment.antnode_version}")
        print(f"  antctl: {deployment.antctl_version}")
    elif deployment.branch:
        print(f"Branch: {deployment.repo_owner}/{deployment.branch}")
    print()

    questions = [
        "Are all nodes running?",
        "Are the bootstrap cache files available?",
        "Is the main dashboard receiving data?",
        "Do nodes on generic hosts have open connections and connected peers?",
        "Do nodes on peer cache hosts have open connections and connected peers?",
        "Do symmetric NAT private nodes have open connections and connected peers?",
        "Do full cone NAT private nodes have open connections and connected peers?",
        "Is ELK receiving logs?",
        "Is `antctl` on the correct version?",
        "Is `antnode` on the correct version?",
        "Are the correct reserved IPs allocated?",
        "Is the client dashboard receiving data?",
        "Do client wallets have funds?",
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
        
        if answer == "No":
            should_continue = questionary.confirm("Abandon the test?").ask()
            if not should_continue:
                for remaining_question in questions[questions.index(question) + 1:]:
                    results[remaining_question] = "N/A"
            break

    repo.record_smoke_test_result(deployment_id, results)
    print("\nRecorded results")

def _build_deployment_and_smoke_test_report(deployment: NetworkDeployment) -> str:
    """Build a detailed report about a specific deployment.
    
    Args:
        deployment: The deployment to format
        
    Returns:
        str: The formatted deployment report
    """
    lines = []
    lines.append(f"*{deployment.name}*")
    lines.append("")

    if deployment.description:
        lines.append(f"{deployment.description}")
    
    lines.append("")
    lines.append("```")
    lines.extend(build_deployment_report(deployment))
    lines.append("```")
        
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("*SMOKE TEST RESULTS*")
    
    repo = NetworkDeploymentRepository()
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

def upload_report(deployment_id: int) -> None:
    """Upload a report for a deployment.
    
    Args:
        deployment_id: ID of the deployment to upload report for
    """
    try:
        repo = NetworkDeploymentRepository()
        deployment = repo.get_by_id(deployment_id)
        if not deployment:
            raise ValueError(f"Deployment with ID {deployment_id} not found")

        start_time = questionary.text("Start time:").ask()
        end_time = questionary.text("End time:").ask()

        total_uploaders = questionary.text(
            "Number of uploaders:",
            validate=lambda text: text.isdigit()
        ).ask()
        successful_uploads = questionary.text(
            "Number of successful uploads:",
            validate=lambda text: text.isdigit()
        ).ask()
        total_chunks = questionary.text(
            "Records uploaded:",
            validate=lambda text: text.isdigit()
        ).ask()
        avg_upload_time = questionary.text(
            "Average upload time (seconds):",
            validate=lambda text: text.replace('.', '').isdigit()
        ).ask()
        chunk_proof_error_count = questionary.text(
            "Number of chunk proof errors:",
            validate=lambda text: text.replace('.', '').isdigit()
        ).ask()
        not_enough_quotes_error_count = questionary.text(
            "Number of not enough quotes errors:",
            validate=lambda text: text.replace('.', '').isdigit()
        ).ask()
        other_error_count = questionary.text(
            "Number of other errors:",
            validate=lambda text: text.replace('.', '').isdigit()
        ).ask()

        start_datetime = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
        end_datetime = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
        duration_seconds = (end_datetime - start_datetime).total_seconds()
        duration_hours = duration_seconds / 3600

        print()
        print("=======")
        print("Uploads")
        print("=======")
        print(f"{deployment.name}")
        print(f"Duration: {duration_hours:.2f} hours")
        print(f"Time slice: {start_time} to {end_time}")
        print(f"- Total uploaders: {total_uploaders}")
        print(f"- Successful uploads: {successful_uploads}")
        print(f"- Total chunks uploaded: {total_chunks}")
        print(f"- Average upload time: {avg_upload_time}s")
        print(f"- Chunk proof errors: {chunk_proof_error_count}")
        print(f"- Not enough quotes errors: {not_enough_quotes_error_count}")
        print(f"- Other errors: {other_error_count}")
    except Exception as e:
        print(f"Error uploading report: {e}")
        sys.exit(1)

def download_report(deployment_id: int) -> None:
    """Generate a report for downloads on a deployment.
    
    Args:
        deployment_id: ID of the deployment to generate download report for
    """
    try:
        repo = NetworkDeploymentRepository()
        deployment = repo.get_by_id(deployment_id)
        if not deployment:
            raise ValueError(f"Deployment with ID {deployment_id} not found")

        start_time = questionary.text("Start time:").ask()
        end_time = questionary.text("End time:").ask()
        
        start_datetime = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
        end_datetime = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
        duration_seconds = (end_datetime - start_datetime).total_seconds()
        duration_hours = duration_seconds / 3600
        
        print("\nStandard Downloader:")
        standard_successful = questionary.text(
            "Successful downloads:",
            validate=lambda text: text.isdigit()
        ).ask()
        standard_errors = questionary.text(
            "Errors:",
            validate=lambda text: text.isdigit()
        ).ask()
        standard_avg_time = questionary.text(
            "Average download time (seconds):",
            validate=lambda text: text.replace('.', '').isdigit()
        ).ask()
        
        print("\nRandom Downloader:")
        random_successful = questionary.text(
            "Successful downloads:",
            validate=lambda text: text.isdigit()
        ).ask()
        random_errors = questionary.text(
            "Errors:",
            validate=lambda text: text.isdigit()
        ).ask()
        random_avg_time = questionary.text(
            "Average download time (seconds):",
            validate=lambda text: text.replace('.', '').isdigit()
        ).ask()
        
        print("\nPerformance Downloader:")
        perf_successful = questionary.text(
            "Successful downloads:",
            validate=lambda text: text.isdigit()
        ).ask()
        perf_errors = questionary.text(
            "Errors:",
            validate=lambda text: text.isdigit()
        ).ask()
        perf_avg_time = questionary.text(
            "Average download time (seconds):",
            validate=lambda text: text.replace('.', '').isdigit()
        ).ask()
        
        print("\n\n")
        print("=========")
        print("Downloads")
        print("=========")
        print(f"{deployment.name}")
        print(f"Time slice: {start_time} to {end_time}")
        print(f"Duration: {duration_hours:.2f} hours")
        print("  Standard Downloader:")
        print(f"    - Successful downloads: {standard_successful}")
        print(f"    - Errors: {standard_errors}")
        print(f"    - Average download time: {standard_avg_time}s")
        print("  Random Downloader:")
        print(f"    - Successful downloads: {random_successful}")
        print(f"    - Errors: {random_errors}")
        print(f"    - Average download time: {random_avg_time}s")
        print("  Performance Downloader:")
        print(f"    - Successful downloads: {perf_successful}")
        print(f"    - Errors: {perf_errors}")
        print(f"    - Average download time: {perf_avg_time}s")
            
    except Exception as e:
        print(f"Error generating download report: {e}")
        sys.exit(1)

def start_clients(network_name: str) -> None:
    """Start clients for a network.
    
    Args:
        network_name: Name of the network to start clients in
    """
    config = {
        "network-name": network_name
    }
    
    print("\nStarting uploaders...")
    start_uploaders(config, "main", force=True, wait=False)
    
    print("\nStarting downloaders...")
    start_downloaders(config, "main", force=True, wait=False)