import os
import requests
import sys

from datetime import datetime, UTC
from typing import List

import questionary
from rich import print as rprint

from runner.db import ClientDeploymentRepository, ComparisonRepository, NetworkDeploymentRepository
from runner.models import DeploymentType
from runner.reporting import build_comparison_report, build_comparison_smoke_test_report

REPO_OWNER = "maidsafe"
REPO_NAME = "sn-testnet-workflows"
AUTONOMI_REPO_NAME = "autonomi"

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

def new(deployment_type: str = "network") -> None:
    """Create a new comparison using interactive prompts."""

    dep_type = DeploymentType.NETWORK if deployment_type == "network" else DeploymentType.CLIENT
    if dep_type == DeploymentType.NETWORK:
        repo = NetworkDeploymentRepository()
        deployment_name = "network deployment"
    else:
        repo = ClientDeploymentRepository()
        deployment_name = "client deployment"
        
    recent_deployments = repo.get_recent_deployments()
    
    if not recent_deployments:
        print(f"No {deployment_name}s found")
        return

    choices = [
        f"{d.name} ({d.created_at.strftime('%Y-%m-%d %H:%M:%S')})"
        for d in recent_deployments
    ]

    description = questionary.text(
        "Description (optional):",
    ).ask()

    ref_choice = questionary.select(
        "Select the reference deployment:",
        choices=choices
    ).ask()
    
    ref_index = choices.index(ref_choice)
    ref_deployment = recent_deployments[ref_index]
    ref_id = ref_deployment.id
    print(f"Reference deployment ID: {ref_id}")

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
        
        test_choice = questionary.select(
            "Select the test deployment:",
            choices=choices
        ).ask()
        
        test_index = choices.index(test_choice)
        test_deployment = recent_deployments[test_index]
        test_id = test_deployment.id
        print(f"Test deployment ID: {test_id}")

        test_label = questionary.text(
            "What is the label for this test environment? (e.g. version number or PR#)",
        ).ask()

        test_envs.append((test_id, test_label))

    comparison_repo = ComparisonRepository()
    comparison_repo.create_comparison(ref_id, test_envs, ref_label, description, dep_type)
    print(f"\nComparison created")

def post(comparison_id: int) -> None:
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

        report = build_comparison_report(comparison)
        smoke_test_report = build_comparison_smoke_test_report(comparison)
        
        if comparison.deployment_type == DeploymentType.NETWORK:
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
        elif comparison.deployment_type == DeploymentType.CLIENT:
            response = requests.post(
                webhook_url,
                json={"text": report + "\n\n" + smoke_test_report},
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            print(f"Posted comparison report to Slack")
        else:
            print(f"Skipping smoke test report for client deployment")
    except requests.exceptions.RequestException as e:
        print(f"Error posting to Slack: {e}")
        sys.exit(1)

def print_comparison(comparison_id: int) -> None:
    """Print detailed information about a specific comparison."""
    try:
        repo = ComparisonRepository()
        comparison = repo.get_by_id(comparison_id)
        if not comparison:
            raise ValueError(f"Comparison with ID {comparison_id} not found")
        report = build_comparison_report(comparison)
        smoke_test_report = build_comparison_smoke_test_report(comparison)
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

def upload_report(comparison_id: int) -> None:
    """Upload a report for a comparison.
    
    Args:
        comparison_id: ID of the comparison to upload report for
    """
    try:
        repo = ComparisonRepository()
        comparison = repo.get_by_id(comparison_id)
        if not comparison:
            raise ValueError(f"Comparison with ID {comparison_id} not found")

        environments = [(dep, label, f"TEST{i+1}") for i, (dep, label) in enumerate(comparison.test_environments)] + \
                       [(comparison.ref_deployment, comparison.ref_label, "REF")]
        
        start_time = questionary.text("Start time:").ask()
        end_time = questionary.text("End time:").ask()
        
        start_datetime = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
        end_datetime = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
        duration_seconds = (end_datetime - start_datetime).total_seconds()
        duration_hours = duration_seconds / 3600
        
        env_reports = []
        
        for deployment, label, env_name in environments:
            print(f"\n{env_name} [{deployment.name}]:")
            print("=" * 50)
            
            total_uploaders = questionary.text(
                "Uploaders:",
                validate=lambda text: text.isdigit()
            ).ask()
            successful_uploads = questionary.text(
                "Successful uploads:",
                validate=lambda text: text.isdigit()
            ).ask()
            records_uploaded = questionary.text(
                "Records uploaded:",
                validate=lambda text: text.isdigit()
            ).ask()
            avg_upload_time = questionary.text(
                "Average upload time (seconds):",
                validate=lambda text: text.replace('.', '').isdigit()
            ).ask()
            chunk_proof_error_count = questionary.text(
                "Chunk proof errors:",
                validate=lambda text: text.replace('.', '').isdigit()
            ).ask()
            not_enough_quotes_error_count = questionary.text(
                "Not enough quotes errors:",
                validate=lambda text: text.replace('.', '').isdigit()
            ).ask()
            other_error_count = questionary.text(
                "Other errors:",
                validate=lambda text: text.replace('.', '').isdigit()
            ).ask()
            
            env_reports.append({
                "env_name": env_name,
                "label": label,
                "name": deployment.name,
                "total_uploaders": total_uploaders,
                "successful_uploads": successful_uploads,
                "records_uploaded": records_uploaded,
                "avg_upload_time": avg_upload_time,
                "chunk_proof_error_count": chunk_proof_error_count,
                "not_enough_quotes_error_count": not_enough_quotes_error_count,
                "other_error_count": other_error_count
            })
        
        print("\n\n")
        print("=======")
        print("Uploads")
        print("=======")
        print(f"Time slice: {start_time} to {end_time}")
        print(f"Duration: {duration_hours:.2f} hours")
        for report in env_reports:
            print()
            print(f"{report['env_name']} [{report['name']}]:")
            print(f"  - Uploaders: {report['total_uploaders']}")
            print(f"  - Successful uploads: {report['successful_uploads']}")
            print(f"  - Records uploaded: {report['records_uploaded']}")
            print(f"  - Average upload time: {report['avg_upload_time']}s")
            print(f"  - Chunk proof errors: {report['chunk_proof_error_count']}")
            print(f"  - Not enough quotes errors: {report['not_enough_quotes_error_count']}")
            print(f"  - Other errors: {report['other_error_count']}")
            
    except Exception as e:
        print(f"Error uploading report: {e}")
        sys.exit(1)

def download_report(comparison_id: int) -> None:
    """Generate a report for downloads on each environment in a comparison.
    
    Args:
        comparison_id: ID of the comparison to generate download report for
    """
    try:
        repo = ComparisonRepository()
        comparison = repo.get_by_id(comparison_id)
        if not comparison:
            raise ValueError(f"Comparison with ID {comparison_id} not found")

        environments = [(dep, label, f"TEST{i+1}") for i, (dep, label) in enumerate(comparison.test_environments)] + \
                       [(comparison.ref_deployment, comparison.ref_label, "REF")]
        
        start_time = questionary.text("Start time:").ask()
        end_time = questionary.text("End time:").ask()
        
        start_datetime = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
        end_datetime = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
        duration_seconds = (end_datetime - start_datetime).total_seconds()
        duration_hours = duration_seconds / 3600
        
        env_reports = []
        
        for deployment, label, env_name in environments:
            print(f"\n{env_name} [{deployment.name}]:")
            print("=" * 50)
            
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
            
            env_reports.append({
                "env_name": env_name,
                "label": label,
                "name": deployment.name,
                "standard_successful": standard_successful,
                "standard_errors": standard_errors,
                "standard_avg_time": standard_avg_time,
                "random_successful": random_successful,
                "random_errors": random_errors,
                "random_avg_time": random_avg_time,
                "perf_successful": perf_successful,
                "perf_errors": perf_errors,
                "perf_avg_time": perf_avg_time
            })
        
        print("\n\n")
        print("=========")
        print("Downloads")
        print("=========")
        print(f"Time slice: {start_time} to {end_time}")
        print(f"Duration: {duration_hours:.2f} hours")
        for report in env_reports:
            print()
            print(f"{report['env_name']} [{report['name']}]:")
            print("  Standard Downloader:")
            print(f"    - Successful downloads: {report['standard_successful']}")
            print(f"    - Errors: {report['standard_errors']}")
            print(f"    - Average download time: {report['standard_avg_time']}s")
            print("  Random Downloader:")
            print(f"    - Successful downloads: {report['random_successful']}")
            print(f"    - Errors: {report['random_errors']}")
            print(f"    - Average download time: {report['random_avg_time']}s")
            print("  Performance Downloader:")
            print(f"    - Successful downloads: {report['perf_successful']}")
            print(f"    - Errors: {report['perf_errors']}")
            print(f"    - Average download time: {report['perf_avg_time']}s")
            
    except Exception as e:
        print(f"Error generating download report: {e}")
        sys.exit(1)
