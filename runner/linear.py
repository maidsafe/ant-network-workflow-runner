import logging
import os
import requests
import sys
from typing import Dict, List, Optional, Tuple

LINEAR_TEAMS = ["Infrastructure", "QA", "Releases", "Tech"]

def get_api_key(team: str) -> str:
    """Get the Linear API key for a team.
    
    Args:
        team: The team name
        
    Returns:
        The Linear API key
        
    Raises:
        ValueError: If the API key environment variable is not set
    """
    api_key_env_var = f"ANT_RUNNER_LINEAR_{team.upper()}_API_KEY"
    linear_api_key = os.getenv(api_key_env_var)
    if not linear_api_key:
        raise ValueError(f"Error: {api_key_env_var} environment variable is not set")
    return linear_api_key

def make_linear_api_request(query: str, variables: Dict, api_key: str) -> Dict:
    """Make a request to the Linear API with error handling.
    
    Args:
        query: The GraphQL query to execute
        variables: The variables for the GraphQL query
        api_key: The Linear API key to use for authentication
        
    Returns:
        The JSON response from the API
        
    Raises:
        Exception: If the request fails or returns GraphQL errors
    """
    try:
        response = requests.post(
            "https://api.linear.app/graphql",
            json={"query": query, "variables": variables},
            headers={
                "Content-Type": "application/json",
                "Authorization": api_key
            }
        )
        
        logging.debug(f"Response status code: {response.status_code}")
        logging.debug(f"Response content: {response.text}")
        
        response.raise_for_status()
        
        result = response.json()
        if "errors" in result:
            error_message = result.get("errors", [])[0].get("message", "Unknown GraphQL error")
            raise Exception(f"GraphQL error: {error_message}")
            
        return result
    except requests.exceptions.RequestException as e:
        print(f"Error making request to Linear API: {e}")
        print(f"Request details:")
        print(f"  - URL: https://api.linear.app/graphql")
        print(f"  - Query: {query}")
        print(f"  - Variables: {variables}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"  - Response status: {e.response.status_code}")
            print(f"  - Response text: {e.response.text}")
        raise

def get_team_id(team: str, api_key: str) -> str:
    """Get the Linear team ID for a team name.
    
    Args:
        team: The team name
        api_key: The Linear API key
        
    Returns:
        The team ID
        
    Raises:
        ValueError: If the team is not found
    """
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
    
    result = make_linear_api_request(teams_query, {}, api_key)
    
    teams = result.get("data", {}).get("teams", {}).get("nodes", [])
    if not teams:
        raise ValueError("No teams found")
        
    team_id = next((t["id"] for t in teams if t["name"] == team), None)
    if not team_id:
        raise ValueError(f"Team ID not found for {team}")
    
    logging.debug(f"Obtained team ID for {team}: {team_id}")
    return team_id

def get_qa_label_id(team_id: str, api_key: str) -> str:
    """Get the Linear QA label ID for a team.
    
    Args:
        team_id: The team ID
        api_key: The Linear API key
        
    Returns:
        The QA label ID
        
    Raises:
        ValueError: If the QA label is not found
    """
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
    
    result = make_linear_api_request(labels_query, {"teamId": team_id}, api_key)
    
    labels = result.get("data", {}).get("team", {}).get("labels", {}).get("nodes", [])
    if not labels:
        raise ValueError(f"No labels found for team ID {team_id}")
        
    qa_label_id = next((label["id"] for label in labels if label["name"].lower() == "qa"), None)
    if not qa_label_id:
        raise ValueError("QA label not found. Please create a 'QA' label in Linear first.")
        
    logging.debug(f"Obtained label ID for QA: {qa_label_id}")
    return qa_label_id

def get_projects(team_id: str, api_key: str) -> List[Dict]:
    """Get the Linear projects for a team.
    
    Args:
        team_id: The team ID
        api_key: The Linear API key
        
    Returns:
        A list of projects with their IDs and names
        
    Raises:
        ValueError: If no projects are found
    """
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
    
    result = make_linear_api_request(projects_query, {"teamId": team_id}, api_key)
    
    projects = result.get("data", {}).get("team", {}).get("projects", {}).get("nodes", [])
    if not projects:
        raise ValueError(f"No projects found for team ID {team_id}")
    
    return projects

def get_project_id(projects: List[Dict], project_name: str) -> str:
    """Get the Linear project ID for a project name.
    
    Args:
        projects: A list of projects with their IDs and names
        project_name: The project name
        
    Returns:
        The project ID
        
    Raises:
        ValueError: If the project is not found
    """
    project_id = next((p["id"] for p in projects if p["name"] == project_name), None)
    if not project_id:
        raise ValueError(f"Project ID not found for {project_name}")
    
    return project_id

def get_in_progress_state_id(team_id: str, api_key: str) -> Optional[str]:
    """Get the Linear 'In Progress' state ID for a team.
    
    Args:
        team_id: The team ID
        api_key: The Linear API key
        
    Returns:
        The 'In Progress' state ID, or None if not found
        
    Raises:
        ValueError: If no workflow states are found
    """
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
    
    result = make_linear_api_request(states_query, {"teamId": team_id}, api_key)
    
    states = result.get("data", {}).get("team", {}).get("states", {}).get("nodes", [])
    if not states:
        raise ValueError(f"No workflow states found for team ID {team_id}")
        
    in_progress_state_id = next((state["id"] for state in states if state["name"].lower() == "in progress"), None)
    if not in_progress_state_id:
        logging.debug(f"Available states: {[state['name'] for state in states]}")
        return None
        
    logging.debug(f"Obtained state ID for 'In Progress': {in_progress_state_id}")
    return in_progress_state_id

def create_issue(title: str, description: str, team_id: str, project_id: str, 
                label_ids: List[str], state_id: Optional[str], api_key: str) -> Tuple[str, str]:
    """Create a Linear issue.
    
    Args:
        title: The issue title
        description: The issue description
        team_id: The team ID
        project_id: The project ID
        label_ids: A list of label IDs to apply to the issue
        state_id: The state ID, or None to use the default state
        api_key: The Linear API key
        
    Returns:
        A tuple of (issue identifier, issue URL)
        
    Raises:
        ValueError: If the issue creation fails
    """
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
        "description": description,
        "teamId": team_id,
        "projectId": project_id,
        "labelIds": label_ids,
        "stateId": state_id
    }
        
    logging.debug(f"Project ID: {project_id}")
    logging.debug(f"Team ID: {team_id}")
    logging.debug(f"Request variables: {variables}")
    
    result = make_linear_api_request(graphql_query, variables, api_key)
    
    if result.get("data", {}).get("issueCreate", {}).get("success"):
        issue = result["data"]["issueCreate"]["issue"]
        return issue['identifier'], issue['url']
    else:
        raise ValueError(f"Failed to create issue. Response data: {result}")

def create_project_update(project_id: str, body: str, api_key: str) -> str:
    """Create a Linear project update.
    
    Args:
        project_id: The project ID
        body: The update body
        api_key: The Linear API key
        
    Returns:
        The project update URL
        
    Raises:
        ValueError: If the project update creation fails
    """
    project_update_query = """
    mutation CreateProjectUpdate($projectId: String!, $body: String!) {
      projectUpdateCreate(input: {
        projectId: $projectId,
        body: $body
      }) {
        success
        projectUpdate {
          id
          url
        }
      }
    }
    """
    
    update_variables = {
        "projectId": project_id,
        "body": body
    }
    
    update_result = make_linear_api_request(project_update_query, update_variables, api_key)
    
    if update_result.get("data", {}).get("projectUpdateCreate", {}).get("success"):
        project_update = update_result["data"]["projectUpdateCreate"]["projectUpdate"]
        return project_update['url']
    else:
        raise ValueError(f"Failed to create project update. Response data: {update_result}")
