import json
import logging
import sys
import time
from enum import Enum
from typing import List, Optional, Dict, Any

import requests
from rich import print as rprint
from rich.progress import Progress, SpinnerColumn, TextColumn

from runner.db import record_workflow_run

class NodeType(Enum):
    BOOTSTRAP = "bootstrap"
    GENESIS = "genesis"
    GENERIC = "generic"
    PRIVATE = "private"
    
    def __str__(self) -> str:
        return self.value

def confirm_workflow_dispatch(workflow_name: str, inputs: Dict[str, Any]) -> bool:
    """
    Display workflow information and prompt for confirmation.
    
    Args:
        workflow_name: Name of the workflow to be dispatched
        inputs: Dictionary of workflow inputs
    
    Returns:
        bool: True if user confirms, False otherwise
    """
    rprint(f"Dispatching the [green]{workflow_name}[/green] workflow with the following inputs:")
    print(json.dumps(inputs, indent=2))
    print("\nProceed? [y/N]: ", end="")
    
    response = input().lower()
    return response in ['y', 'yes']

class WorkflowRun:
    def __init__(self, owner: str, repo: str, id: int, 
                 personal_access_token: str, branch_name: str, name: str):
        self.owner = owner
        self.repo = repo
        self.id = id
        self.personal_access_token = personal_access_token
        self.branch_name = branch_name
        self.name = name

    def _trigger_workflow(self) -> requests.Response:
        """Trigger the workflow via GitHub API."""
        url = f"https://api.github.com/repos/{self.owner}/{self.repo}/actions/workflows/{self.id}/dispatches"
        
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.personal_access_token}",
        }
        
        data = {
            "ref": self.branch_name,
            "inputs": self.get_workflow_inputs()
        }

        logging.debug("Request URL: %s", url)
        logging.debug("Request payload: %s", data)
        
        return requests.post(url, headers=headers, json=data)

    def _get_workflow_run_id(self) -> int:
        """Get the ID of the most recently triggered workflow run."""
        url = f"https://api.github.com/repos/{self.owner}/{self.repo}/actions/workflows/{self.id}/runs"
        
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.personal_access_token}",
        }
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        workflow_runs = response.json().get("workflow_runs", [])
        
        for run in workflow_runs:
            if run["status"] != "completed":
                return run["id"]
        
        raise RuntimeError("Could not find workflow run ID for recently triggered workflow")

    def _display_spinner(self, seconds: int) -> None:
        """Display a spinner in the terminal for the specified number of seconds."""
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            task = progress.add_task("Waiting for workflow run to be available...", total=None)
            time.sleep(seconds)

    def run(self, force: bool = False) -> None:
        """
        Trigger the workflow run and record it in the database.
        
        Args:
            force: If True, skip confirmation prompt
        """
        inputs = self.get_workflow_inputs()
        
        if not force:
            if not confirm_workflow_dispatch(self.name, inputs):
                sys.exit(0)
        else:
            rprint(f"Dispatching the [green]{self.name}[/green] workflow...")
        
        response = self._trigger_workflow()
        response.raise_for_status()
        
        self._display_spinner(2)
        
        run_id = self._get_workflow_run_id()
        
        record_workflow_run(
            workflow_name=self.name,
            branch_name=self.branch_name,
            network_name=self.network_name,
            inputs=inputs,
            run_id=run_id
        )
        
        print()
        print("Workflow run:")
        print(f"https://github.com/{self.owner}/{self.repo}/actions/runs/{run_id}")
        print()

    def get_workflow_inputs(self) -> Dict[str, Any]:
        """Get workflow-specific inputs. Should be overridden by subclasses."""
        return {}

class StopNodesWorkflowRun(WorkflowRun):
    def __init__(self, owner: str, repo: str, id: int, 
                 personal_access_token: str, branch_name: str,
                 network_name: str, ansible_forks: Optional[int] = None, 
                 custom_inventory: Optional[List[str]] = None,
                 delay: Optional[int] = None, 
                 interval: Optional[int] = None,
                 node_type: Optional[NodeType] = None,
                 testnet_deploy_args: Optional[str] = None):
        super().__init__(owner, repo, id, personal_access_token, branch_name, name="Stop Nodes")
        self.network_name = network_name
        self.ansible_forks = ansible_forks
        self.custom_inventory = custom_inventory
        self.delay = delay
        self.interval = interval
        self.node_type = node_type
        self.testnet_deploy_args = testnet_deploy_args

    def get_workflow_inputs(self) -> Dict[str, Any]:
        """Get inputs specific to the stop nodes workflow."""
        inputs = {
            "network-name": self.network_name,
        }
        
        if self.ansible_forks is not None:
            inputs["ansible-forks"] = str(self.ansible_forks)
        if self.custom_inventory is not None:
            inputs["custom-inventory"] = ",".join(self.custom_inventory)
        if self.delay is not None:
            inputs["delay"] = str(self.delay)
        if self.interval is not None:
            inputs["interval"] = str(self.interval)
        if self.node_type is not None:
            inputs["node-type"] = self.node_type.value
        if self.testnet_deploy_args is not None and self.testnet_deploy_args.strip():
            inputs["testnet-deploy-args"] = self.testnet_deploy_args
            
        return inputs

class UpgradeNodeManagerWorkflow(WorkflowRun):
    def __init__(self, owner: str, repo: str, id: int,
                 personal_access_token: str, branch_name: str,
                 network_name: str, version: str,
                 custom_inventory: Optional[List[str]] = None,
                 node_type: Optional[NodeType] = None,
                 testnet_deploy_args: Optional[str] = None):
        super().__init__(owner, repo, id, personal_access_token, branch_name, name="Upgrade Node Manager")
        self.network_name = network_name
        self.version = version
        self.custom_inventory = custom_inventory
        self.node_type = node_type
        self.testnet_deploy_args = testnet_deploy_args

    def get_workflow_inputs(self) -> Dict[str, Any]:
        """Get inputs specific to the upgrade node manager workflow."""
        inputs = {
            "network-name": self.network_name,
            "version": self.version
        }
        
        if self.custom_inventory is not None:
            inputs["custom-inventory"] = ",".join(self.custom_inventory)
        if self.node_type is not None:
            inputs["node-type"] = self.node_type.value
        if self.testnet_deploy_args is not None and self.testnet_deploy_args.strip():
            inputs["testnet-deploy-args"] = self.testnet_deploy_args
            
        return inputs

class DestroyNetworkWorkflow(WorkflowRun):
    def __init__(self, owner: str, repo: str, id: int,
                 personal_access_token: str, branch_name: str,
                 network_name: str, testnet_deploy_args: Optional[str] = None):
        super().__init__(owner, repo, id, personal_access_token, branch_name, name="Destroy Network")
        self.network_name = network_name
        self.testnet_deploy_args = testnet_deploy_args

    def get_workflow_inputs(self) -> Dict[str, Any]:
        """Get inputs specific to the destroy network workflow."""
        inputs = {
            "network-name": self.network_name,
        }
        
        if self.testnet_deploy_args is not None and self.testnet_deploy_args.strip():
            inputs["testnet-deploy-args"] = self.testnet_deploy_args
            
        return inputs

class StopTelegrafWorkflow(WorkflowRun):
    def __init__(self, owner: str, repo: str, id: int, 
                 personal_access_token: str, branch_name: str,
                 network_name: str, ansible_forks: Optional[int] = None, 
                 custom_inventory: Optional[List[str]] = None,
                 delay: Optional[int] = None,
                 node_type: Optional[NodeType] = None,
                 testnet_deploy_args: Optional[str] = None):
        super().__init__(owner, repo, id, personal_access_token, branch_name, name="Stop Telegraf")
        self.network_name = network_name
        self.ansible_forks = ansible_forks
        self.custom_inventory = custom_inventory
        self.delay = delay
        self.node_type = node_type
        self.testnet_deploy_args = testnet_deploy_args

    def get_workflow_inputs(self) -> Dict[str, Any]:
        """Get inputs specific to the stop telegraf workflow."""
        inputs = {
            "network-name": self.network_name,
        }
        
        if self.ansible_forks is not None:
            inputs["ansible-forks"] = str(self.ansible_forks)
        if self.custom_inventory is not None:
            inputs["custom-inventory"] = ",".join(self.custom_inventory)
        if self.delay is not None:
            inputs["delay"] = str(self.delay)
        if self.node_type is not None:
            inputs["node-type"] = self.node_type.value
        if self.testnet_deploy_args is not None and self.testnet_deploy_args.strip():
            inputs["testnet-deploy-args"] = self.testnet_deploy_args
            
        return inputs

class UpgradeNetworkWorkflow(WorkflowRun):
    def __init__(self, owner: str, repo: str, id: int,
                 personal_access_token: str, branch_name: str,
                 network_name: str, version: str,
                 ansible_forks: Optional[int] = None,
                 custom_inventory: Optional[List[str]] = None,
                 delay: Optional[int] = None,
                 interval: Optional[int] = None,
                 node_type: Optional[NodeType] = None,
                 testnet_deploy_args: Optional[str] = None):
        super().__init__(owner, repo, id, personal_access_token, branch_name, name="Upgrade Network")
        self.network_name = network_name
        self.version = version
        self.ansible_forks = ansible_forks
        self.custom_inventory = custom_inventory
        self.delay = delay
        self.interval = interval
        self.node_type = node_type
        self.testnet_deploy_args = testnet_deploy_args

    def get_workflow_inputs(self) -> Dict[str, Any]:
        """Get inputs specific to the upgrade network workflow."""
        inputs = {
            "network-name": self.network_name,
            "version": self.version
        }
        
        if self.ansible_forks is not None:
            inputs["ansible-forks"] = str(self.ansible_forks)
        if self.custom_inventory is not None:
            inputs["custom-inventory"] = ",".join(self.custom_inventory)
        if self.delay is not None:
            inputs["delay"] = str(self.delay)
        if self.interval is not None:
            inputs["interval"] = str(self.interval)
        if self.node_type is not None:
            inputs["node-type"] = self.node_type.value
        if self.testnet_deploy_args is not None and self.testnet_deploy_args.strip():
            inputs["testnet-deploy-args"] = self.testnet_deploy_args
            
        return inputs