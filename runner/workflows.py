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
    return response in ["y", "yes"]

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

    def run(self, force: bool = False) -> int:
        """
        Trigger the workflow run and record it in the database.
        
        Args:
            force: If True, skip confirmation prompt
        
        Returns:
            int: The workflow run ID
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
        
        attempts = 0
        max_attempts = 3
        while attempts < max_attempts:
            try:
                run_id = self._get_workflow_run_id()
                break
            except RuntimeError:
                attempts += 1
                if attempts == max_attempts:
                    raise
                self._display_spinner(5)
        
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
        
        return run_id

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

class StartTelegrafWorkflow(WorkflowRun):
    def __init__(self, owner: str, repo: str, id: int, 
                 personal_access_token: str, branch_name: str,
                 network_name: str, ansible_forks: Optional[int] = None, 
                 custom_inventory: Optional[List[str]] = None,
                 delay: Optional[int] = None,
                 node_type: Optional[NodeType] = None,
                 testnet_deploy_args: Optional[str] = None):
        super().__init__(owner, repo, id, personal_access_token, branch_name, name="Start Telegraf")
        self.network_name = network_name
        self.ansible_forks = ansible_forks
        self.custom_inventory = custom_inventory
        self.delay = delay
        self.node_type = node_type
        self.testnet_deploy_args = testnet_deploy_args

    def get_workflow_inputs(self) -> Dict[str, Any]:
        """Get inputs specific to the start telegraf workflow."""
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

class UpdatePeerWorkflow(WorkflowRun):
    def __init__(self, owner: str, repo: str, id: int,
                 personal_access_token: str, branch_name: str,
                 network_name: str, peer: str,
                 custom_inventory: Optional[List[str]] = None,
                 node_type: Optional[NodeType] = None):
        super().__init__(owner, repo, id, personal_access_token, branch_name, name="Update Peer")
        self.network_name = network_name
        self.peer = peer
        self.custom_inventory = custom_inventory
        self.node_type = node_type

    def get_workflow_inputs(self) -> Dict[str, Any]:
        """Get inputs specific to the update peer workflow."""
        inputs = {
            "network-name": self.network_name,
            "peer": self.peer
        }
        
        if self.custom_inventory is not None:
            inputs["custom-inventory"] = ",".join(self.custom_inventory)
        if self.node_type is not None:
            inputs["node-type"] = self.node_type.value
            
        return inputs

class UpgradeUploadersWorkflow(WorkflowRun):
    def __init__(self, owner: str, repo: str, id: int,
                 personal_access_token: str, branch_name: str,
                 network_name: str, version: str,
                 testnet_deploy_args: Optional[str] = None):
        super().__init__(owner, repo, id, personal_access_token, branch_name, name="Upgrade Uploaders")
        self.network_name = network_name
        self.version = version
        self.testnet_deploy_args = testnet_deploy_args

    def get_workflow_inputs(self) -> Dict[str, Any]:
        """Get inputs specific to the upgrade uploaders workflow."""
        inputs = {
            "network-name": self.network_name,
            "version": self.version
        }
        
        if self.testnet_deploy_args is not None and self.testnet_deploy_args.strip():
            inputs["testnet-deploy-args"] = self.testnet_deploy_args
            
        return inputs

class LaunchNetworkWorkflow(WorkflowRun):
    def __init__(self, owner: str, repo: str, id: int,
                 personal_access_token: str, branch_name: str, network_name: str,
                 config: Dict[str, Any]):
        super().__init__(owner, repo, id, personal_access_token, branch_name, name="Launch Network")
        self.network_name = network_name
        self.config = config
        self._validate_config()

    def _validate_config(self) -> None:
        """Validate the configuration inputs."""
        required_fields = ["network-name", "environment-type", "rewards-address"]
        for field in required_fields:
            if field not in self.config:
                raise KeyError(field)
                
        has_versions = any([
            "autonomi-version" in self.config,
            "safenode-version" in self.config,
            "safenode-manager-version" in self.config
        ])
        
        has_build_config = any([
            "branch" in self.config,
            "repo-owner" in self.config
        ])
        
        if has_versions and has_build_config:
            raise ValueError("Cannot specify both binary versions and build configuration")
            
        if not has_versions and not has_build_config:
            raise ValueError("Must specify either binary versions or build configuration")
            
        if has_build_config and ('branch' not in self.config or 'repo-owner' not in self.config):
            raise ValueError("Both branch and repo-owner must be specified for build configuration")

    def get_workflow_inputs(self) -> Dict[str, Any]:
        """Get inputs specific to the launch network workflow."""
        inputs = {
            "network-name": self.config["network-name"],
            "environment-type": self.config["environment-type"],
        }

        if all(key in self.config for key in ["autonomi-version", "safenode-version", "safenode-manager-version"]):
            inputs["bin-versions"] = f"{self.config['autonomi-version']},{self.config['safenode-version']},{self.config['safenode-manager-version']}"

        node_counts = []
        for count_type in ["bootstrap-node-count", "generic-node-count", "private-node-count", 
                          "downloader-count", "uploader-count"]:
            if count_type in self.config:
                node_counts.append(str(self.config[count_type]))
                
        vm_counts = []
        for count_type in ["bootstrap-vm-count", "generic-vm-count", "private-vm-count", 
                          "uploader-vm-count"]:
            if count_type in self.config:
                vm_counts.append(str(self.config[count_type]))
                
        if node_counts and vm_counts:
            inputs["node-vm-counts"] = f"({', '.join(node_counts)}), ({', '.join(vm_counts)})"

        deploy_args = []
        deploy_arg_mappings = {
            "bootstrap-node-vm-size": "--bootstrap-node-vm-size",
            "branch": "--branch",
            "chunk-size": "--chunk-size",
            "evm-network-type": "--evm-network-type",
            "evm-node-vm-size": "--evm-node-vm-size",
            "interval": "--interval",
            "max-archived-log-files": "--max-archived-log-files",
            "max-log-files": "--max-log-files",
            "node-vm-size": "--node-vm-size",
            "public-rpc": "--public-rpc",
            "repo-owner": "--repo-owner",
            "rewards-address": "--rewards-address",
            "safenode-features": "--safenode-features",
            "uploader-vm-size": "--uploader-vm-size"
        }
        
        for config_key, arg_name in deploy_arg_mappings.items():
            if config_key in self.config:
                value = self.config[config_key]
                if isinstance(value, bool):
                    if value:
                        deploy_args.append(arg_name)
                else:
                    deploy_args.append(f"{arg_name} {value}")
        
        if deploy_args:
            inputs["deploy-args"] = " ".join(deploy_args)

        if "environment-vars" in self.config:
            inputs["environment-vars"] = self.config["environment-vars"]

        testnet_deploy_args = []
        if "testnet-deploy-branch" in self.config:
            testnet_deploy_args.append(f"--branch {self.config['testnet-deploy-branch']}")
        if "testnet-deploy-repo-owner" in self.config:
            testnet_deploy_args.append(f"--repo-owner {self.config['testnet-deploy-repo-owner']}")
        if "testnet-deploy-version" in self.config:
            testnet_deploy_args.append(f"--version {self.config['testnet-deploy-version']}")
            
        if testnet_deploy_args:
            inputs["testnet-deploy-args"] = " ".join(testnet_deploy_args)

        return inputs

class KillDropletsWorkflow(WorkflowRun):
    def __init__(self, owner: str, repo: str, id: int,
                 personal_access_token: str, branch_name: str,
                 network_name: str, droplet_names: List[str]):
        super().__init__(owner, repo, id, personal_access_token, branch_name, name="Kill Droplets")
        self.network_name = network_name
        self.droplet_names = droplet_names

    def get_workflow_inputs(self) -> Dict[str, Any]:
        """Get inputs specific to the kill droplets workflow."""
        return {
            "droplet-names": ",".join(self.droplet_names)
        }