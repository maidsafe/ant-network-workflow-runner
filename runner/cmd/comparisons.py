import os
import requests
import sys

from datetime import datetime, UTC
from typing import List

import questionary
from rich import print as rprint

from runner.db import ComparisonRepository, DeploymentRepository
from runner.models import Comparison, Deployment

def add_thread(comparison_id: int, thread_link: str) -> None:
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

def ls() -> None:
    """List all recorded comparisons."""
    repo = ComparisonRepository()
    comparisons = repo.list_comparisons()
    if not comparisons:
        print("No comparisons found.")
        return
        
    print("=" * 100)
    print(" " * 35 + "C O M P A R I S O N S" + " " * 35)
    print("=" * 100)
    
    print(f"{'ID':<5} {'Title':<40} {'Created':<20}")
    print("-" * 100)
    
    for comparison in comparisons:
        created_at = comparison.created_at.strftime("%Y-%m-%d %H:%M:%S")
        rprint(f"{comparison.id:<5} {comparison.title:<40} {created_at:<20}")
        
    print("\nAll times are in UTC")

def new() -> None:
    """Create a new comparison using interactive prompts."""

    description = questionary.text(
        "Description (optional):",
    ).ask()

    ref_id = questionary.text(
        "What is the ID of the reference deployment?",
        validate=lambda text: text.isdigit() and int(text) > 0 or "Please enter a valid deployment ID"
    ).ask()
    ref_id = int(ref_id)

    ref_label = questionary.text(
        "What is the label for the reference environment? (e.g. version number/PR#/branch ref)",
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
        repo = ComparisonRepository()
        comparison = repo.get_by_id(comparison_id)
        if not comparison:
            raise ValueError(f"Comparison with ID {comparison_id} not found")

        report = _build_comparison_report(comparison)
        smoke_test_report = _build_smoke_test_report(comparison)
        
        response = requests.post(
            webhook_url,
            json={"text": report},
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        print(f"Posted comparison report to Slack")

        response = requests.post(
            webhook_url,
            json={"text": smoke_test_report},
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        print(f"Posted smoke test report to Slack")
    except requests.exceptions.RequestException as e:
        print(f"Error posting to Slack: {e}")
        sys.exit(1)

def print(comparison_id: int) -> None:
    """Print detailed information about a specific comparison."""
    try:
        repo = ComparisonRepository()
        comparison = repo.get_by_id(comparison_id)
        if not comparison:
            raise ValueError(f"Comparison with ID {comparison_id} not found")
        report = _build_comparison_report(comparison)
        smoke_test_report = _build_smoke_test_report(comparison)
        full_report = f"{report}\n\n{smoke_test_report}"
        print(full_report)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

def record_results(comparison_id: int, started_at: str, ended_at: str, report_path: str, passed: bool) -> None:
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

def _build_comparison_report(comparison: Comparison) -> str:
    """Build a detailed report about a specific comparison.
    
    Args:
        comparison_id: ID of the comparison to report on
        
    Returns:
        str: The formatted comparison report
    """
    lines = []
    lines.append("*ENVIRONMENT COMPARISON*")
    lines.append("")

    if comparison.description:
        lines.append(f"{comparison.description}")
        lines.append("")

    if comparison.thread_link:
        lines.append(f"Slack thread: {comparison.thread_link}")

    lines.append(f"*REF*: {comparison.ref_label} [`{comparison.ref_deployment.name}`]")
    n = 1
    for test_deployment in comparison.test_environments:
        (deployment, label) = test_deployment
        lines.append(f"*TEST{n}*: {label} [`{deployment.name}`]")
        n += 1

    lines.append("")
    lines.append("---")
    lines.append("")
    n = 1
    for test_deployment in comparison.test_environments:
        (deployment, label) = test_deployment
        lines.append(f"*TEST{n}*: {label} [`{deployment.name}`]")
        lines.append("```")
        lines.extend(_build_deployment_report(deployment))
        lines.append("```")
        lines.append("")
        n += 1

    lines.append(f"*REF*: {comparison.ref_label} [`{comparison.ref_deployment.name}`]")
    lines.append("```")
    lines.extend(_build_deployment_report(comparison.ref_deployment))
    lines.append("```")

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

def _build_smoke_test_report(comparison: Comparison) -> str:
    """Build a smoke test report for a comparison.
    
    Args:
        comparison: The comparison to build the report for
        
    Returns:
        str: The formatted smoke test report
    """
    lines = []
    lines.append("*SMOKE TEST RESULTS*")
    lines.append("")
    
    repo = DeploymentRepository()
    
    n = 1
    for test_deployment, label in comparison.test_environments:
        results = repo.get_smoke_test_result(test_deployment.id)
        if not results:
            lines.append(f"*TEST{n}*: {label} [`{test_deployment.name}`]")
            lines.append("No smoke test results recorded")
            lines.append("")
            continue
            
        lines.append(f"*TEST{n}*: {label} [`{test_deployment.name}`]")
        for question, answer in results.results.items():
            status = {
                "Yes": "✅ ",
                "No": "❌ ",
                "N/A": "N/A"
            }.get(answer, "?")
            lines.append(f"{status}  {question}")
        lines.append("")
        lines.append(f"---")
        lines.append("")
        n += 1
    
    ref_results = repo.get_smoke_test_result(comparison.ref_deployment.id)
    lines.append(f"*REF*: {comparison.ref_label} [`{comparison.ref_deployment.name}`]")
    if not ref_results:
        lines.append("No smoke test results recorded")
    else:
        for question, answer in ref_results.results.items():
            status = {
                "Yes": "✅ ",
                "No": "❌ ",
                "N/A": "N/A"
            }.get(answer, "?")
            lines.append(f"{status}  {question}")
    
    return "\n".join(lines)