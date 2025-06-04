import requests
import os
import sys
from datetime import datetime

import questionary
from rich import print as rprint

from runner.db import ClientDeploymentRepository
from runner.models import ClientDeployment
from runner.reporting import build_client_deployment_report
from runner.linear import LINEAR_TEAMS, get_api_key, get_team_id, get_qa_label_id, get_projects, get_project_id, get_in_progress_state_id, create_issue, create_project_update

REPO_OWNER = "maidsafe"
REPO_NAME = "sn-testnet-workflows"
AUTONOMI_REPO_NAME = "autonomi"

def ls(show_details: bool = False) -> None:
    """List all recorded client deployments."""
    try:
        repo = ClientDeploymentRepository()
        deployments = repo.list_client_deployments()
        if not deployments:
            print("No client deployments found.")
            return
            
        print("=" * 61)
        print(" " * 12 + "C L I E N T   D E P L O Y M E N T S" + " " * 12)
        print("=" * 61)
        
        if show_details:
            for deployment in deployments:
                lines = []
                lines.append(f"*{deployment.name}*")
                lines.append("")
                if deployment.description:
                    lines.append(f"Description: {deployment.description}")
                lines.extend(build_client_deployment_report(deployment))
                rprint("\n".join(lines))
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
        print(f"Error: Failed to retrieve client deployments: {e}")
        sys.exit(1)

def print_deployment(deployment_id: int) -> None:
    """Print detailed information about a specific deployment.
    
    Args:
        deployment_id: ID of the deployment to print
    """
    repo = ClientDeploymentRepository()
    deployment = repo.get_by_id(deployment_id)
    if not deployment:
        print(f"Error: client deployment with ID {deployment_id} not found")
        sys.exit(1)
        
    report = _build_deployment_and_smoke_test_report(deployment)
    print(report)

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
        repo = ClientDeploymentRepository()
        deployment = repo.get_by_id(deployment_id)
        if not deployment:
            raise ValueError(f"Client deployment with ID {deployment_id} not found")

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

def smoke_test(deployment_id: int) -> None:
    """Run a smoke test for a deployment.
    
    Args:
        deployment_id: ID of the deployment to test
    """
    repo = ClientDeploymentRepository()
    deployment = repo.get_by_id(deployment_id)
    if not deployment:
        print(f"Error: Client deployment with ID {deployment_id} not found")
        sys.exit(1)

    print(f"\nSmoke test for {deployment.name}")
    print("-" * 40)

    if deployment.ant_version:
        print(f"Versions:")
        print(f"  ant: {deployment.ant_version}")
    elif deployment.branch:
        print(f"Branch: {deployment.repo_owner}/{deployment.branch}")
    print()

    questions = [
        "Is the client dashboard receiving data?",
        "Do client wallets have funds?",
        "Is `ant` on the correct version?",
        "Do the uploaders have no errors?",
        "Do the downloaders have no errors?",
        "Do the performance downloaders have no errors?",
        "Do the random downloaders have no errors?"
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
            should_continue = questionary.confirm("Continue the test?").ask()
            if not should_continue:
                for remaining_question in questions[questions.index(question) + 1:]:
                    results[remaining_question] = "N/A"
                break

    repo.record_smoke_test_result(deployment_id, results)
    print("\nRecorded results")

def upload_report(deployment_id: int) -> None:
    """Upload a report for a deployment.
    
    Args:
        deployment_id: ID of the deployment to upload report for
    """
    try:
        repo = ClientDeploymentRepository()
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
    """Generate a report for downloads on a client deployment.
    
    Args:
        deployment_id: ID of the client deployment to generate download report for
    """
    try:
        repo = ClientDeploymentRepository()
        deployment = repo.get_by_id(deployment_id)
        if not deployment:
            raise ValueError(f"Client deployment with ID {deployment_id} not found")

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

def _build_deployment_and_smoke_test_report(deployment: ClientDeployment) -> str:
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
    lines.extend(build_client_deployment_report(deployment))
    lines.append("```")
        
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("*SMOKE TEST RESULTS*")
    
    repo = ClientDeploymentRepository()
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

def linear(deployment_id: int) -> None:
    """Create an issue in Linear for a client deployment.
    
    Args:
        deployment_id: ID of the client deployment to create an issue for
    """
    try:
        repo = ClientDeploymentRepository()
        deployment = repo.get_by_id(deployment_id)
        if not deployment:
            raise ValueError(f"Client deployment with ID {deployment_id} not found")

        test_type = questionary.select(
            "What type of test was this client deployment created for?",
            choices=["Upload Performance Test", "Download Performance Test", "Upload/Download Performance Test"]
        ).ask()
        if test_type is None:
            print("Test type selection cancelled")
            return
        
        team = questionary.select(
            "Select team:",
            choices=LINEAR_TEAMS
        ).ask()
        
        try:
            api_key = get_api_key(team)
            team_id = get_team_id(team, api_key)
            qa_label_id = get_qa_label_id(team_id, api_key)
            projects = get_projects(team_id, api_key)
            
            project_choices = sorted([p["name"] for p in projects])
            project_name = questionary.select(
                "Select project:",
                choices=project_choices
            ).ask()
            
            project_id = get_project_id(projects, project_name)
            in_progress_state_id = get_in_progress_state_id(team_id, api_key)
            
            label = None
            if deployment.related_pr:
                label = f"#{deployment.related_pr}"
            elif deployment.branch:
                label = f"{deployment.repo_owner}/{deployment.branch}"
            else:
                raise ValueError("No related PR or branch found for the deployment")
            title = f"{test_type}: `{label}` [{deployment.name}]"
                
            report = _build_deployment_and_smoke_test_report(deployment)
            issue_identifier, issue_url = create_issue(
                title=title,
                description=report,
                team_id=team_id,
                project_id=project_id,
                label_ids=[qa_label_id],
                state_id=in_progress_state_id,
                api_key=api_key
            )
            
            print(f"Created issue {issue_identifier}: {issue_url}")
            
            update_url = create_project_update(
                project_id=project_id,
                body=report,
                api_key=api_key
            )
            
            print(f"Created project update: {update_url}")
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)
    except Exception as e:
        import traceback
        print(f"Error: {e}")
        print(traceback.format_exc())
        sys.exit(1)