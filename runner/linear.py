import logging
import os
import requests
import sys
from enum import Enum
from typing import Dict, List, Optional, Tuple

class Team(Enum):
    INFRASTRUCTURE = "Infrastructure"
    QA = "QA"
    RELEASES = "Releases"
    TECH = "Tech"

class ProjectLabel(Enum):
    RELEASE = "Release"
    RC = "RC"

def get_team_id(team: Team) -> str:
    """Get the Linear team ID for a team name.
    
    Args:
        team: The team
        
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
    
    result = _make_linear_api_request(teams_query, {}, team)
    
    teams = result.get("data", {}).get("teams", {}).get("nodes", [])
    if not teams:
        raise ValueError("No teams found")
        
    team_id = next((t["id"] for t in teams if t["name"] == team.value), None)
    if not team_id:
        raise ValueError(f"Team ID not found for {team.value}")
    
    logging.debug(f"Obtained team ID for {team.value}: {team_id}")
    return team_id

def get_qa_label_id(team: Team) -> str:
    """Get the Linear QA label ID for a team.
    
    Args:
        team: The team
        
    Returns:
        The QA label ID
        
    Raises:
        ValueError: If the QA label is not found
    """
    team_id = get_team_id(team)
    
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
    
    result = _make_linear_api_request(labels_query, {"teamId": team_id}, team)
    
    labels = result.get("data", {}).get("team", {}).get("labels", {}).get("nodes", [])
    if not labels:
        raise ValueError(f"No labels found for team ID {team_id}")
        
    qa_label_id = next((label["id"] for label in labels if label["name"].lower() == "qa"), None)
    if not qa_label_id:
        raise ValueError("QA label not found. Please create a 'QA' label in Linear first.")
        
    logging.debug(f"Obtained label ID for QA: {qa_label_id}")
    return qa_label_id

def get_projects(team: Team) -> List[Dict]:
    """Get the Linear projects for a team.
    
    Args:
        team: The team
        
    Returns:
        A list of projects with their IDs and names
        
    Raises:
        ValueError: If no projects are found
    """
    team_id = get_team_id(team)
    
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
    
    result = _make_linear_api_request(projects_query, {"teamId": team_id}, team)
    
    projects = result.get("data", {}).get("team", {}).get("projects", {}).get("nodes", [])
    if not projects:
        raise ValueError(f"No projects found for team ID {team_id}")
    
    return projects

def get_project_id(name: str, team: Team) -> str:
    """Get the Linear project ID for a project name.
    
    Args:
        name: The project name
        team: The team
        
    Returns:
        The project ID
        
    Raises:
        ValueError: If the project is not found
    """
    team_id = get_team_id(team)
    
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
    
    result = _make_linear_api_request(projects_query, {"teamId": team_id}, team)
    
    projects = result.get("data", {}).get("team", {}).get("projects", {}).get("nodes", [])
    if not projects:
        raise ValueError(f"No projects found for team ID {team_id}")
    
    project_id = next((p["id"] for p in projects if p["name"] == name), None)
    if not project_id:
        raise ValueError(f"Project ID not found for {name}")
    
    return project_id

def get_state_id(name: str, team: Team) -> str:
    """Get the Linear state ID for a team by state name.
    
    Args:
        name: The state name to search for
        team: The team
        
    Returns:
        The state ID
        
    Raises:
        ValueError: If no workflow states are found or if the requested state is not found
    """
    team_id = get_team_id(team)
    
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
    
    result = _make_linear_api_request(states_query, {"teamId": team_id}, team)
    
    states = result.get("data", {}).get("team", {}).get("states", {}).get("nodes", [])
    if not states:
        raise ValueError(f"No workflow states found for team ID {team_id}")
        
    state_id = next((state["id"] for state in states if state["name"].lower() == name.lower()), None)
    if not state_id:
        available_states = [state['name'] for state in states]
        raise ValueError(f"State '{name}' not found. Available states: {available_states}")
        
    logging.debug(f"Obtained state ID for '{name}': {state_id}")
    return state_id

def create_issue(title: str, description: str, team: Team, project_id: str, 
                label_ids: List[str], state_id: Optional[str]) -> Tuple[str, str]:
    """Create a Linear issue.
    
    Args:
        title: The issue title
        description: The issue description
        team: The team
        project_id: The project ID
        label_ids: A list of label IDs to apply to the issue
        state_id: The state ID, or None to use the default state
        
    Returns:
        A tuple of (issue identifier, issue URL)
        
    Raises:
        ValueError: If the issue creation fails
    """
    team_id = get_team_id(team)
    
    graphql_query = """
    mutation CreateIssue($title: String!, $description: String, $teamId: String!, $projectId: String!, $labelIds: [String!], $stateId: String) {
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
    
    result = _make_linear_api_request(graphql_query, variables, team)
    
    if result.get("data", {}).get("issueCreate", {}).get("success"):
        issue = result["data"]["issueCreate"]["issue"]
        print(f"Created issue with ID {issue['identifier']}")
        return issue["identifier"], issue["url"]
    else:
        raise ValueError(f"Failed to create issue. Response data: {result}")

def create_project(name: str, description: str, content: str, team: Team):
    """Create a Linear project.
    
    Args:
        name: The project name
        description: The project description
        content: The project content
        team: The team
        project_labels: Optional list of project labels to apply
        
    Returns:
        The project ID
        
    Raises:
        ValueError: If the project creation fails
    """
    team_id = get_team_id(team)
    
    create_project_query = """
    mutation CreateProject($name: String!, $teamIds: [String!]!, $description: String, $content: String) {
      projectCreate(input: {
        name: $name,
        description: $description,
        content: $content,
        teamIds: $teamIds
      }) {
        success
        project {
          id
        }
      }
    }
    """
    
    variables = {
        "name": name,
        "description": description,
        "content": content,
        "teamIds": [team_id],
    }
    
    result = _make_linear_api_request(create_project_query, variables, team)
    
    if result.get("data", {}).get("projectCreate", {}).get("success"):
        project_id = result["data"]["projectCreate"]["project"]["id"]
        print(f"Created project {name} with ID {project_id}")
        return project_id
    else:
        print(f"Failed to create new project")
        sys.exit(1)

def create_project_update(project_id: str, body: str, team: Team) -> str:
    """Create a Linear project update.
    
    Args:
        project_id: The project ID
        body: The update body
        team: The team
        
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
    
    update_result = _make_linear_api_request(project_update_query, update_variables, team)
    
    if update_result.get("data", {}).get("projectUpdateCreate", {}).get("success"):
        project_update = update_result["data"]["projectUpdateCreate"]["projectUpdate"]
        print(f"Created project update with URL {project_update['url']}")
        return project_update['url']
    else:
        raise ValueError(f"Failed to create project update. Response data: {update_result}")

def _get_api_key(team: Team) -> str:
    """Get the Linear API key for a team.
    
    Args:
        team: The team
        
    Returns:
        The Linear API key
        
    Raises:
        ValueError: If the API key environment variable is not set
    """
    api_key_env_var = f"ANT_RUNNER_LINEAR_{team.value.upper()}_API_KEY"
    linear_api_key = os.getenv(api_key_env_var)
    if not linear_api_key:
        raise ValueError(f"Error: {api_key_env_var} environment variable is not set")
    return linear_api_key

def _make_linear_api_request(query: str, variables: Dict, team: Team) -> Dict:
    """Make a request to the Linear API with error handling.
    
    Args:
        query: The GraphQL query to execute
        variables: The variables for the GraphQL query
        team: The team to get the API key for
        
    Returns:
        The JSON response from the API
        
    Raises:
        Exception: If the request fails or returns GraphQL errors
    """
    api_key = _get_api_key(team)
    
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
