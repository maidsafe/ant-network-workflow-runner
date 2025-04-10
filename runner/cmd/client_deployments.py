import sys
from datetime import datetime

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
            print(f"{'ID':<5} {'Name':<15} {'Env Type':<15} {'Deployed':<20} {'PR#':<15}")
            print("-" * 70)
            
            for deployment in deployments:
                related_pr = f"#{deployment.related_pr}" if deployment.related_pr else "-"
                timestamp = deployment.triggered_at.strftime("%Y-%m-%d %H:%M:%S")
                
                rprint(f"{deployment.id:<5} [green]{deployment.name:<15}[/green] {deployment.environment_type:<15} {timestamp:<20} {related_pr:<15}")
                print(f"  https://github.com/{REPO_OWNER}/{REPO_NAME}/actions/runs/{deployment.run_id}")
                
        print("\nAll times are in UTC")
    except Exception as e:
        print(f"Error: Failed to retrieve client deployments: {e}")
        sys.exit(1)