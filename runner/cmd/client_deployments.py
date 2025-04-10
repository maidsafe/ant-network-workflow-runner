import sys
from datetime import datetime

import questionary
from rich import print as rprint

from runner.db import ClientDeploymentRepository
from runner.models import ClientDeployment
from runner.reporting import build_client_deployment_report

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
                lines = build_client_deployment_report(deployment)
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
            should_continue = questionary.confirm("Abandon the test?").ask()
            if not should_continue:
                for remaining_question in questions[questions.index(question) + 1:]:
                    results[remaining_question] = "N/A"
            break

    repo.record_smoke_test_result(deployment_id, results)
    print("\nRecorded results")