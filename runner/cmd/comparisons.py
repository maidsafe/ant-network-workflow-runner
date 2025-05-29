import logging
import os
import requests
import sys

from datetime import datetime, UTC
from typing import List, Dict, Optional

import questionary
from rich import print as rprint

from runner.db import ClientDeploymentRepository, ComparisonRepository, NetworkDeploymentRepository
from runner.models import DeploymentType
from runner.reporting import build_comparison_report, build_comparison_smoke_test_report

REPO_OWNER = "maidsafe"
REPO_NAME = "sn-testnet-workflows"
AUTONOMI_REPO_NAME = "autonomi"

LINEAR_TEAMS = ["Infrastructure", "Releases", "Tech"]

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
    
    print(f"{'ID':<5} {'Title':<40} {'Created':<20} {'Type':<10}")
    print("-" * 100)
    
    for comparison in comparisons:
        created_at = comparison.created_at.strftime("%Y-%m-%d %H:%M:%S")
        rprint(f"{comparison.id:<5} {comparison.title:<40} {created_at:<20} {comparison.deployment_type:<10}")
        
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

def linear(comparison_id: int) -> None:
    """Create an issue in Linear for a comparison.
    
    Args:
        comparison_id: ID of the comparison to create an issue for
    """
    try:
        repo = ComparisonRepository()
        comparison = repo.get_by_id(comparison_id)
        if not comparison:
            raise ValueError(f"Comparison with ID {comparison_id} not found")

        report = build_comparison_report(comparison)
        smoke_test_report = build_comparison_smoke_test_report(comparison)
        
        if comparison.deployment_type == DeploymentType.NETWORK:
            full_report = f"{report}\n\n{smoke_test_report}"
        elif comparison.deployment_type == DeploymentType.CLIENT:
            full_report = f"{report}\n\n{smoke_test_report}"
        else:
            full_report = report
        
        team = questionary.select(
            "Select team:",
            choices=LINEAR_TEAMS
        ).ask()
        
        api_key_env_var = f"ANT_RUNNER_LINEAR_{team.upper()}_API_KEY"
        linear_api_key = os.getenv(api_key_env_var)
        if not linear_api_key:
            print(f"Error: {api_key_env_var} environment variable is not set")
            sys.exit(1)
        
        teams_query = """
        {
          teams {
            nodes {
              id
              name
            }
          }
        }
        """
        
        response = requests.post(
            "https://api.linear.app/graphql",
            json={"query": teams_query},
            headers={
                "Content-Type": "application/json",
                "Authorization": linear_api_key
            }
        )
        response.raise_for_status()
        
        result = response.json()
        if "errors" in result:
            print(f"Error fetching Linear teams: {result['errors']}")
            sys.exit(1)
        
        teams = result.get("data", {}).get("teams", {}).get("nodes", [])
        if not teams:
            print("No teams found")
            sys.exit(1)
            
        team_id = next((t["id"] for t in teams if t["name"] == team), None)
        if not team_id:
            print(f"Team ID not found for {team}")
            sys.exit(1)

        logging.debug(f"Obtained team ID for {team}: {team_id}")
        
        labels_query = """
        query GetLabels($teamId: String!) {
          team(id: $teamId) {
            labels {
              nodes {
                id
                name
              }
            }
          }
        }
        """
        
        response = requests.post(
            "https://api.linear.app/graphql",
            json={"query": labels_query, "variables": {"teamId": team_id}},
            headers={
                "Content-Type": "application/json",
                "Authorization": linear_api_key
            }
        )
        response.raise_for_status()
        
        result = response.json()
        if "errors" in result:
            print(f"Error fetching Linear labels: {result['errors']}")
            sys.exit(1)
        
        labels = result.get("data", {}).get("team", {}).get("labels", {}).get("nodes", [])
        if not labels:
            print(f"No labels found for team {team}")
            sys.exit(1)
            
        qa_label_id = next((label["id"] for label in labels if label["name"].lower() == "qa"), None)
        if not qa_label_id:
            print("QA label not found. Please create a 'QA' label in Linear first.")
            sys.exit(1)
            
        logging.debug(f"Obtained label ID for QA: {qa_label_id}")
            
        projects_query = """
        query GetProjects($teamId: String!) {
          team(id: $teamId) {
            projects {
              nodes {
                id
                name
              }
            }
          }
        }
        """
        
        response = requests.post(
            "https://api.linear.app/graphql",
            json={"query": projects_query, "variables": {"teamId": team_id}},
            headers={
                "Content-Type": "application/json",
                "Authorization": linear_api_key
            }
        )
        response.raise_for_status()
        
        result = response.json()
        if "errors" in result:
            print(f"Error fetching Linear projects: {result['errors']}")
            sys.exit(1)
        
        projects = result.get("data", {}).get("team", {}).get("projects", {}).get("nodes", [])
        if not projects:
            print(f"No projects found for team {team}")
            sys.exit(1)
        
        project_choices = sorted([p["name"] for p in projects])
        project_name = questionary.select(
            "Select project:",
            choices=project_choices
        ).ask()
        
        project_id = next((p["id"] for p in projects if p["name"] == project_name), None)
        if not project_id:
            print(f"Project ID not found for {project_name}")
            sys.exit(1)
        
        states_query = """
        query GetWorkflowStates($teamId: String!) {
          team(id: $teamId) {
            states {
              nodes {
                id
                name
              }
            }
          }
        }
        """
        
        response = requests.post(
            "https://api.linear.app/graphql",
            json={"query": states_query, "variables": {"teamId": team_id}},
            headers={
                "Content-Type": "application/json",
                "Authorization": linear_api_key
            }
        )
        response.raise_for_status()
        
        result = response.json()
        if "errors" in result:
            print(f"Error fetching Linear workflow states: {result['errors']}")
            sys.exit(1)
        
        states = result.get("data", {}).get("team", {}).get("states", {}).get("nodes", [])
        if not states:
            print(f"No workflow states found for team {team}")
            sys.exit(1)
            
        in_progress_state_id = next((state["id"] for state in states if state["name"].lower() == "in progress"), None)
        if not in_progress_state_id:
            print("'In Progress' state not found for this team. The issue will be created with the default state.")
            logging.debug(f"Available states: {[state['name'] for state in states]}")
            sys.exit(1)
            
        logging.debug(f"Obtained state ID for 'In Progress': {in_progress_state_id}")
        
        if comparison.deployment_type == DeploymentType.NETWORK:
            title = "Environment Comparison: "
            for i, (deployment, label) in enumerate(comparison.test_environments):
                if label.isdigit():
                    label = f"#{label}"
                title += f"`{label}` [{deployment.name}]"
                if i < len(comparison.test_environments) - 1:
                    title += " vs "
            title += f" vs `{comparison.ref_label}` [{comparison.ref_deployment.name}]"
        else:
            title = "Client Comparison: "
            for i, (_, label) in enumerate(comparison.test_environments):
                if label.isdigit():
                    label = f"#{label}"
                title += f"`{label}` [{deployment.name}]"
                if i < len(comparison.test_environments) - 1:
                    title += " vs "
            title += f" vs `{comparison.ref_label}` [{comparison.ref_deployment.name}]"
        
        graphql_query = """
        mutation CreateIssue($title: String!, $description: String!, $teamId: String!, $projectId: String!, $labelIds: [String!], $stateId: String) {
          issueCreate(input: {
            title: $title,
            description: $description,
            teamId: $teamId,
            projectId: $projectId,
            labelIds: $labelIds,
            stateId: $stateId
          }) {
            success
            issue {
              id
              identifier
              url
            }
          }
        }
        """
        
        variables = {
            "title": title,
            "description": full_report,
            "teamId": team_id,
            "projectId": project_id,
            "labelIds": [qa_label_id],
            "stateId": in_progress_state_id
        }
            
        logging.debug(f"Project ID: {project_id}")
        logging.debug(f"Team ID: {team_id}")
        logging.debug(f"Request variables: {variables}")
        
        try:
            response = requests.post(
                "https://api.linear.app/graphql",
                json={"query": graphql_query, "variables": variables},
                headers={
                    "Content-Type": "application/json",
                    "Authorization": linear_api_key
                }
            )
            
            logging.debug(f"Response status code: {response.status_code}")
            logging.debug(f"Response content: {response.text}")
            
            response.raise_for_status()
            
            result = response.json()
            if "errors" in result:
                print(f"GraphQL errors: {result['errors']}")
                sys.exit(1)
                
            if result.get("data", {}).get("issueCreate", {}).get("success"):
                issue = result["data"]["issueCreate"]["issue"]
                print(f"Created issue {issue['identifier']}: {issue['url']}")
            else:
                print(f"Failed to create issue. Response data: {result}")
                sys.exit(1)
        except requests.exceptions.RequestException as e:
            print(f"Error making request to Linear API: {e}")
            print(f"Request details:")
            print(f"  - URL: https://api.linear.app/graphql")
            print(f"  - Query: {graphql_query}")
            print(f"  - Variables: {variables}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"  - Response status: {e.response.status_code}")
                print(f"  - Response text: {e.response.text}")
            sys.exit(1)
    except Exception as e:
        import traceback
        print(f"Error: {e}")
        print(traceback.format_exc())
        sys.exit(1)