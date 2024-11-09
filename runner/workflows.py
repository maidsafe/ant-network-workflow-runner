from enum import Enum
from typing import List, Optional, Dict, Any
import requests
from runner.db import record_workflow_run

class NodeType(Enum):
    BOOTSTRAP = "bootstrap"
    GENESIS = "genesis"
    GENERIC = "generic"
    PRIVATE = "private"
    
    def __str__(self) -> str:
        return self.value

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

        print("Request URL:", url)
        print("Request payload:", data)
        
        return requests.post(url, headers=headers, json=data)

    def run(self) -> None:
        """Trigger the workflow run and record it in the database."""
        response = self._trigger_workflow()
        response.raise_for_status()
        
        record_workflow_run(
            workflow_name=self.name,
            branch_name=self.branch_name,
            network_name=self.network_name,
            inputs=self.get_workflow_inputs()
        )

    def get_workflow_inputs(self) -> Dict[str, Any]:
        """Get workflow-specific inputs. Should be overridden by subclasses."""
        return {}

class StopNodesWorkflowRun(WorkflowRun):
    def __init__(self, owner: str, repo: str, id: int, 
                 personal_access_token: str, branch_name: str,
                 network_name: str, ansible_forks: Optional[int] = None, 
                 custom_inventory: Optional[List[str]] = None, delay: Optional[int] = None, 
                 interval: Optional[int] = None, node_type: Optional[NodeType] = None,
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
        if self.testnet_deploy_args is not None:
            inputs["testnet-deploy-args"] = self.testnet_deploy_args
            
        return inputs