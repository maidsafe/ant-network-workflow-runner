import json
import logging
import sys
import time
from datetime import datetime, UTC
from enum import Enum
from typing import List, Optional, Dict, Any

import requests
from rich import print as rprint
from rich.progress import Progress, SpinnerColumn, TextColumn

from runner.db import WorkflowRunRepository
from runner.models import WorkflowRun as WorkflowRunModel

class NodeType(Enum):
    GENERIC = "generic"
    GENESIS = "genesis"
    FULL_CONE_PRIVATE = "full-cone-private"
    PEER_CACHE = "peer-cache"
    SYMMETRIC_PRIVATE = "symmetric-private"
    
    def __str__(self) -> str:
        return self.value

NETWORK_IDS = {
    "DEV-01": 3, "DEV-02": 4, "DEV-03": 5, "DEV-04": 6, "DEV-05": 7,
    "DEV-06": 8, "DEV-07": 9, "DEV-08": 10, "DEV-09": 11, "DEV-10": 12,
    "DEV-11": 13, "DEV-12": 14, "DEV-13": 15, "DEV-14": 16, "DEV-15": 17,
    "STG-01": 18, "STG-02": 19, "STG-03": 20, "STG-04": 21, "STG-05": 23,
    "STG-06": 24, "STG-07": 25, "STG-08": 26, "STG-09": 27, "STG-10": 28,
    "STG-11": 29, "STG-12": 30, "STG-13": 31, "STG-14": 32, "STG-15": 33
}

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

class WorkflowRunFailedError(Exception):
    """Exception raised when a workflow run fails."""
    def __init__(self, run_id, conclusion):
        self.run_id = run_id
        self.conclusion = conclusion
        super().__init__(f"Workflow run {run_id} failed with conclusion: {conclusion}")

class WorkflowRun:
    def __init__(self, owner: str, repo: str, id: int, 
                 personal_access_token: str, branch_name: str, name: str):
        self.owner = owner
        self.repo = repo
        self.id = id
        self.personal_access_token = personal_access_token
        self.branch_name = branch_name
        self.name = name
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "Authorization": f"token {personal_access_token}"
        }

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
        
        active_runs = [run for run in workflow_runs if run["status"] != "completed"]
        if not active_runs:
            raise RuntimeError("Could not find workflow run ID for recently triggered workflow")
        
        from datetime import datetime
        active_runs.sort(key=lambda x: datetime.fromisoformat(x["created_at"].replace('Z', '+00:00')), reverse=True)
        
        return active_runs[0]["id"]

    def _display_spinner(self, seconds: int) -> None:
        """Display a spinner in the terminal for the specified number of seconds."""
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            task = progress.add_task("Waiting for workflow run to be available...", total=None)
            time.sleep(seconds)

    def run(self, force: bool = False, wait: bool = False) -> int:
        """
        Trigger the workflow run.
        
        Args:
            force: If True, skip confirmation prompt
            wait: If True, wait for workflow completion
            
        Returns:
            int: The workflow run ID
            
        Raises:
            requests.exceptions.RequestException: If the API request fails
            WorkflowRunFailedError: If waiting for completion and the workflow fails
        """
        if not force:
            self._confirm_workflow()
            
        run_id = self._dispatch_workflow()
        
        if wait:
            self._wait_for_completion(run_id)
            
        return run_id

    def _wait_for_completion(self, run_id: int, poll_interval: int = 30) -> None:
        """
        Wait for the workflow run to complete.
        
        Args:
            run_id: The workflow run ID to monitor
            poll_interval: Time in seconds between status checks
            
        Raises:
            WorkflowRunFailedError: If the workflow run completes with a non-success conclusion
        """
        print(f"\nWaiting for workflow run {run_id} to complete...")
        
        max_retries = 5
        retry_delay = 5
        
        while True:
            try:
                status = self._get_run_status(run_id)
                if status == "completed":
                    url = f"https://api.github.com/repos/{self.owner}/{self.repo}/actions/runs/{run_id}/attempts/1"
                    
                    for retry in range(max_retries):
                        try:
                            response = requests.get(url, headers=self.headers)
                            response.raise_for_status()
                            conclusion = response.json().get("conclusion")
                            
                            print(f"\nWorkflow run {run_id} completed with conclusion: {conclusion}")
                            if conclusion != "success":
                                raise WorkflowRunFailedError(run_id, conclusion)
                            return
                        except (requests.exceptions.RequestException, requests.exceptions.ConnectionError, 
                                requests.exceptions.Timeout, requests.exceptions.SSLError) as e:
                            if retry < max_retries - 1:
                                print(f"Error getting conclusion, retrying in {retry_delay} seconds: {str(e)}")
                                time.sleep(retry_delay)
                                retry_delay *= 1.5  # Exponential backoff
                            else:
                                print(f"Max retries exceeded when getting conclusion: {str(e)}")
                                raise
                
                print(".", end="", flush=True)
                time.sleep(poll_interval)
            except (requests.exceptions.RequestException, requests.exceptions.ConnectionError, 
                    requests.exceptions.Timeout, requests.exceptions.SSLError) as e:
                print(f"\nNetwork error when checking status, retrying in {retry_delay} seconds: {str(e)}")
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 1.5, 60)  # Exponential backoff with a maximum of 60 seconds

    def _get_run_status(self, run_id: int) -> Optional[str]:
        """
        Get the current status of a workflow run.
        
        Args:
            run_id: The workflow run ID
            
        Returns:
            str: The current status of the run
            
        Raises:
            requests.exceptions.RequestException: If the API request fails
        """
        url = f"https://api.github.com/repos/{self.owner}/{self.repo}/actions/runs/{run_id}"
        
        max_retries = 3
        retry_delay = 3
        
        for retry in range(max_retries):
            try:
                response = requests.get(url, headers=self.headers)
                response.raise_for_status()
                return response.json().get("status")
            except (requests.exceptions.RequestException, requests.exceptions.ConnectionError, 
                    requests.exceptions.Timeout, requests.exceptions.SSLError) as e:
                if retry < max_retries - 1:
                    if retry > 0:  # Only log after the first failure
                        print(f"\nError getting status, retrying in {retry_delay} seconds: {str(e)}")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    raise

    def get_workflow_inputs(self) -> Dict[str, Any]:
        """Get workflow-specific inputs. Should be overridden by subclasses."""
        return {}

    def _confirm_workflow(self) -> None:
        """
        Display workflow information and prompt for confirmation.
        
        Raises:
            SystemExit: If user does not confirm
        """
        inputs = self.get_workflow_inputs()
        if not confirm_workflow_dispatch(self.name, inputs):
            sys.exit(0)
        else:
            rprint(f"Dispatching the [green]{self.name}[/green] workflow...")

    def _dispatch_workflow(self) -> int:
        """
        Trigger the workflow and get its run ID.
        
        Returns:
            int: The workflow run ID
            
        Raises:
            requests.exceptions.RequestException: If the API request fails
            RuntimeError: If unable to get workflow run ID after multiple attempts
        """
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
        
        repo = WorkflowRunRepository()
        workflow_run = WorkflowRunModel(
            workflow_name=self.name,
            triggered_at=datetime.now(UTC),
            branch_name=self.branch_name,
            network_name=self.network_name,
            inputs=self.get_workflow_inputs(),
            run_id=run_id
        )
        repo.save(workflow_run)
        
        print()
        print("Workflow run:")
        print(f"https://github.com/{self.owner}/{self.repo}/actions/runs/{run_id}")
        print()
        
        return run_id

    def _build_testnet_deploy_args(self, config: Dict[str, Any]) -> Optional[str]:
        """
        Build testnet-deploy-args string from config inputs.
        
        Args:
            config: Dictionary containing configuration values
            
        Returns:
            str: The constructed testnet-deploy-args string
        """
        testnet_deploy_args = []
        if "testnet-deploy-branch" in config:
            testnet_deploy_args.append(f"--branch {config['testnet-deploy-branch']}")
        if "testnet-deploy-repo-owner" in config:
            testnet_deploy_args.append(f"--repo-owner {config['testnet-deploy-repo-owner']}")
        if "testnet-deploy-version" in config:
            testnet_deploy_args.append(f"--version {config['testnet-deploy-version']}")
            
        if testnet_deploy_args:
            return " ".join(testnet_deploy_args)
        return None

class StopNodesWorkflowRun(WorkflowRun):
    def __init__(self, owner: str, repo: str, id: int, 
                 personal_access_token: str, branch_name: str,
                 network_name: str, ansible_forks: Optional[int] = None, 
                 custom_inventory: Optional[List[str]] = None,
                 delay: Optional[int] = None, 
                 interval: Optional[int] = None,
                 node_type: Optional[NodeType] = None,
                 service_names: Optional[List[str]] = None,
                 testnet_deploy_args: Optional[str] = None):
        super().__init__(owner, repo, id, personal_access_token, branch_name, name="Stop Nodes")
        self.network_name = network_name
        self.ansible_forks = ansible_forks
        self.custom_inventory = custom_inventory
        self.delay = delay
        self.interval = interval
        self.node_type = node_type
        self.service_names = service_names
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
        if self.service_names is not None:
            inputs["service-names"] = ",".join(self.service_names)
        if self.testnet_deploy_args is not None and self.testnet_deploy_args.strip():
            inputs["testnet-deploy-args"] = self.testnet_deploy_args
            
        return inputs

class UpgradeAntctlWorkflow(WorkflowRun):
    def __init__(self, owner: str, repo: str, id: int,
                 personal_access_token: str, branch_name: str,
                 network_name: str, version: str,
                 custom_inventory: Optional[List[str]] = None,
                 node_type: Optional[NodeType] = None,
                 testnet_deploy_args: Optional[str] = None):
        super().__init__(owner, repo, id, personal_access_token, branch_name, name="Upgrade Antctl")
        self.network_name = network_name
        self.version = version
        self.custom_inventory = custom_inventory
        self.node_type = node_type
        self.testnet_deploy_args = testnet_deploy_args

    def get_workflow_inputs(self) -> Dict[str, Any]:
        """Get inputs specific to the upgrade antctl workflow."""
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
                 force: Optional[bool] = None,
                 testnet_deploy_args: Optional[str] = None):
        super().__init__(owner, repo, id, personal_access_token, branch_name, name="Upgrade Network")
        self.network_name = network_name
        self.version = version
        self.ansible_forks = ansible_forks
        self.custom_inventory = custom_inventory
        self.delay = delay
        self.interval = interval
        self.node_type = node_type
        self.force = force
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
        if self.force is not None:
            inputs["force"] = str(self.force).lower()
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

class UpgradeClientsWorkflow(WorkflowRun):
    def __init__(self, owner: str, repo: str, id: int,
                 personal_access_token: str, branch_name: str,
                 network_name: str, version: str,
                 testnet_deploy_args: Optional[str] = None):
        super().__init__(owner, repo, id, personal_access_token, branch_name, name="Upgrade Clients")
        self.network_name = network_name
        self.version = version
        self.testnet_deploy_args = testnet_deploy_args

    def get_workflow_inputs(self) -> Dict[str, Any]:
        """Get inputs specific to the upgrade clients workflow."""
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
                
        if "network-id" not in self.config:
            if self.network_name not in NETWORK_IDS:
                raise ValueError(f"Network name '{self.network_name}' not supported")
            self.config["network-id"] = NETWORK_IDS[self.network_name]
        else:
            network_id = self.config["network-id"]
            if not isinstance(network_id, int) or network_id < 1 or network_id > 255:
                raise ValueError("network-id must be an integer between 1 and 255")

        has_versions = any([
            "ant-version" in self.config,
            "antnode-version" in self.config,
            "antctl-version" in self.config
        ])
        
        has_build_config = any([
            "branch" in self.config,
            "repo-owner" in self.config
        ])
        
        if has_versions and has_build_config:
            raise ValueError("Cannot specify both binary versions and build configuration")
            
        if has_build_config and ('branch' not in self.config or 'repo-owner' not in self.config):
            raise ValueError("Both branch and repo-owner must be specified for build configuration")

    def get_workflow_inputs(self) -> Dict[str, Any]:
        """Get inputs specific to the launch network workflow."""
        inputs = {
            "network-name": self.config["network-name"],
            "environment-type": self.config["environment-type"],
        }

        if all(key in self.config for key in ["ant-version", "antnode-version", "antctl-version"]):
            inputs["bin-versions"] = f"{self.config['ant-version']},{self.config['antnode-version']},{self.config['antctl-version']}"

        node_counts = []
        for count_type in ["peer-cache-node-count", "generic-node-count", "full-cone-private-node-count", 
                          "symmetric-private-node-count", "uploader-count"]:
            if count_type in self.config:
                node_counts.append(str(self.config[count_type]))
                
        vm_counts = []
        for count_type in ["peer-cache-vm-count", "generic-vm-count", "full-cone-private-vm-count", 
                          "symmetric-private-vm-count", "client-vm-count"]:
            if count_type in self.config:
                vm_counts.append(str(self.config[count_type]))
                
        if node_counts and vm_counts:
            inputs["node-vm-counts"] = f"({', '.join(node_counts)}), ({', '.join(vm_counts)})"

        deploy_args = []
        deploy_arg_mappings = {
            "branch": "--branch",
            "chunk-size": "--chunk-size",
            "client-vm-size": "--client-vm-size",
            "disable-download-verifier": "--disable-download-verifier",
            "disable-performance-verifier": "--disable-performance-verifier",
            "disable-random-verifier": "--disable-random-verifier",
            "disable-telegraf": "--disable-telegraf",
            "evm-network-type": "--evm-network-type",
            "evm-data-payments-address": "--evm-data-payments-address",
            "evm-node-vm-size": "--evm-node-vm-size",
            "evm-payment-token-address": "--evm-payment-token-address",
            "evm-rpc-url": "--evm-rpc-url",
            "full-cone-vm-size": "--full-cone-vm-size",
            "initial-gas": "--initial-gas",
            "initial-tokens": "--initial-tokens",
            "interval": "--interval",
            "max-archived-log-files": "--max-archived-log-files",
            "max-log-files": "--max-log-files",
            "network-dashboard-branch": "--network-dashboard-branch",
            "network-id": "--network-id",
            "node-vm-size": "--node-vm-size",
            "peer-cache-node-vm-size": "--peer-cache-node-vm-size",
            "public-rpc": "--public-rpc",
            "region": "--region",
            "repo-owner": "--repo-owner",
            "rewards-address": "--rewards-address",
            "upload-interval": "--upload-interval",
        }
        
        for config_key, arg_name in deploy_arg_mappings.items():
            if config_key in self.config:
                value = self.config[config_key]
                if isinstance(value, bool):
                    if value:
                        deploy_args.append(arg_name)
                else:
                    deploy_args.append(f"{arg_name} {value}")

        if "antnode-features" in self.config:
            features = self.config["antnode-features"]
            if isinstance(features, list):
                features_str = ",".join(features)
                deploy_args.append(f"--antnode-features {features_str}")
            else:
                deploy_args.append(f"--antnode-features {features}")
        
        if deploy_args:
            inputs["deploy-args"] = " ".join(deploy_args)

        if "client-env" in self.config:
            inputs["client-env"] = self.config["client-env"]
        if "node-env" in self.config:
            inputs["node-env"] = self.config["node-env"]

        if "stop-clients" in self.config:
            inputs["stop-clients"] = self.config["stop-clients"]

        testnet_deploy_args = self._build_testnet_deploy_args(self.config)
        if testnet_deploy_args:
            inputs["testnet-deploy-args"] = testnet_deploy_args

        return inputs

class ClientDeployWorkflow(WorkflowRun):
    def __init__(self, owner: str, repo: str, id: int,
                 personal_access_token: str, branch_name: str, deployment_name: str,
                 config: Dict[str, Any]):
        super().__init__(owner, repo, id, personal_access_token, branch_name, name="Client Deploy")
        self.deployment_name = deployment_name
        # The network name field is mandatory to process all workflows in a uniform manner, even
        # though it doesn't really apply to the client deploy workflow.
        self.network_name = deployment_name
        self.config = config
        self._validate_config()

    def _validate_config(self) -> None:
        """Validate the configuration inputs."""
        required_fields = ["deployment-name", "environment-type", "network-id"]
        for field in required_fields:
            if field not in self.config:
                raise KeyError(field)
                
        network_id = self.config["network-id"]
        if not isinstance(network_id, int) or network_id < 1 or network_id > 255:
            raise ValueError("network-id must be an integer between 1 and 255")
                
        has_version = "ant-version" in self.config
        
        has_build_config = any([
            "branch" in self.config,
            "repo-owner" in self.config
        ])
        
        if has_version and has_build_config:
            raise ValueError("Cannot specify both binary version and build configuration")
            
        if has_build_config and ('branch' not in self.config or 'repo-owner' not in self.config):
            raise ValueError("Both branch and repo-owner must be specified for build configuration")

    def get_workflow_inputs(self) -> Dict[str, Any]:
        """Get inputs specific to the client deploy workflow."""
        inputs = {
            "name": self.deployment_name,
            "environment-type": self.config["environment-type"],
            "network-id": str(self.config["network-id"])
        }

        if "ant-version" in self.config:
            inputs["ant-version"] = self.config["ant-version"]
        if "provider" in self.config:
            inputs["provider"] = self.config["provider"]
        if "wallet-secret-keys" in self.config:
            inputs["wallet-secret-key"] = ",".join(self.config["wallet-secret-keys"])

        client_deploy_args = []
        client_deploy_arg_mappings = {
            "ansible-forks": "--ansible-forks",
            "ansible-verbose": "--ansible-verbose",
            "branch": "--branch",
            "chunk-size": "--chunk-size",
            "client-env": "--client-env",
            "client-vm-count": "--client-vm-count",
            "client-vm-size": "--client-vm-size",
            "disable-download-verifier": "--disable-download-verifier",
            "disable-performance-verifier": "--disable-performance-verifier",
            "disable-random-verifier": "--disable-random-verifier",
            "disable-telegraf": "--disable-telegraf",
            "disable-uploaders": "--disable-uploaders",
            "evm-data-payments-address": "--evm-data-payments-address",
            "evm-network-type": "--evm-network-type",
            "evm-payment-token-address": "--evm-payment-token-address",
            "evm-rpc-url": "--evm-rpc-url",
            "expected-hash": "--expected-hash",
            "expected-size": "--expected-size",
            "file-address": "--file-address",
            "initial-gas": "--initial-gas",
            "initial-tokens": "--initial-tokens",
            "max-uploads": "--max-uploads",
            "network-contacts-url": "--network-contacts-url",
            "peer": "--peer",
            "region": "--region",
            "repo-owner": "--repo-owner",
            "uploaders-count": "--uploaders-count",
            "upload-interval": "--upload-interval",
            "upload-size": "--upload-size"
        }
        
        for config_key, arg_name in client_deploy_arg_mappings.items():
            if config_key in self.config:
                value = self.config[config_key]
                if isinstance(value, bool):
                    if value:
                        client_deploy_args.append(arg_name)
                else:
                    client_deploy_args.append(f"{arg_name} {value}")
                    
        if client_deploy_args:
            inputs["client-deploy-args"] = " ".join(client_deploy_args)

        testnet_deploy_args = self._build_testnet_deploy_args(self.config)
        if testnet_deploy_args:
            inputs["testnet-deploy-args"] = testnet_deploy_args

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

class UpscaleNetworkWorkflow(WorkflowRun):
    def __init__(self, owner: str, repo: str, id: int,
                 personal_access_token: str, branch_name: str,
                 network_name: str, config: Dict[str, Any]):
        super().__init__(owner, repo, id, personal_access_token, branch_name, name="Upscale Network")
        self.network_name = network_name
        self.config = config

    def get_workflow_inputs(self) -> Dict[str, Any]:
        """Get inputs specific to the upscale network workflow."""
        inputs = {
            "network-name": self.network_name,
        }

        upscale_args = []
        upscale_arg_mappings = {
            "ansible-verbose": "--ansible-verbose",
            "antctl-version": "--antctl-version",
            "antnode-version": "--antnode-version",
            "ant-version": "--ant-version",
            "branch": "--branch",
            "desired-client-vm-count": "--desired-client-vm-count",
            "desired-node-count": "--desired-node-count",
            "desired-node-vm-count": "--desired-node-vm-count",
            "desired-peer-cache-node-count": "--desired-peer-cache-node-count",
            "desired-peer-cache-node-vm-count": "--desired-peer-cache-node-vm-count",
            "desired-full-cone-private-node-count": "--desired-full-cone-private-node-count",
            "desired-full-cone-private-node-vm-count": "--desired-full-cone-private-node-vm-count",
            "desired-symmetric-private-node-count": "--desired-symmetric-private-node-count",
            "desired-symmetric-private-node-vm-count": "--desired-symmetric-private-node-vm-count",
            "desired-uploaders-count": "--desired-uploaders-count",
            "funding-wallet-secret-key": "--funding-wallet-secret-key",
            "infra-only": "--infra-only",
            "interval": "--interval",
            "max-archived-log-files": "--max-archived-log-files",
            "max-log-files": "--max-log-files",
            "network-dashboard-branch": "--network-dashboard-branch",
            "plan": "--plan",
            "provider": "--provider",
            "public-rpc": "--public-rpc",
            "repo-owner": "--repo-owner"
        }

        for config_key, arg_name in upscale_arg_mappings.items():
            if config_key in self.config:
                value = self.config[config_key]
                if isinstance(value, bool):
                    if value:
                        upscale_args.append(arg_name)
                else:
                    upscale_args.append(f"{arg_name} {value}")

        if "node-env" in self.config:
            inputs["node-env"] = self.config["node-env"]
        if upscale_args:
            inputs["upscale-args"] = " ".join(upscale_args)

        testnet_deploy_args = self._build_testnet_deploy_args(self.config)
        if testnet_deploy_args:
            inputs["testnet-deploy-args"] = testnet_deploy_args

        return inputs

class DepositFundsWorkflow(WorkflowRun):
    def __init__(self, owner: str, repo: str, id: int,
                 personal_access_token: str, branch_name: str,
                 network_name: str, provider: str,
                 funding_wallet_secret_key: Optional[str] = None,
                 gas_to_transfer: Optional[str] = None,
                 tokens_to_transfer: Optional[str] = None,
                 testnet_deploy_args: Optional[str] = None):
        super().__init__(owner, repo, id, personal_access_token, branch_name, name="Deposit Funds")
        self.network_name = network_name
        self.provider = provider
        self.funding_wallet_secret_key = funding_wallet_secret_key
        self.gas_to_transfer = gas_to_transfer
        self.tokens_to_transfer = tokens_to_transfer
        self.testnet_deploy_args = testnet_deploy_args

    def get_workflow_inputs(self) -> Dict[str, Any]:
        """Get inputs specific to the deposit funds workflow."""
        inputs = {
            "network-name": self.network_name,
            "provider": self.provider
        }
        
        if self.funding_wallet_secret_key is not None:
            inputs["funding-wallet-secret-key"] = self.funding_wallet_secret_key
        if self.gas_to_transfer is not None:
            inputs["gas-to-transfer"] = self.gas_to_transfer
        if self.tokens_to_transfer is not None:
            inputs["tokens-to-transfer"] = self.tokens_to_transfer
        if self.testnet_deploy_args is not None and self.testnet_deploy_args.strip():
            inputs["testnet-deploy-args"] = self.testnet_deploy_args
            
        return inputs

class StartNodesWorkflow(WorkflowRun):
    def __init__(self, owner: str, repo: str, id: int, 
                 personal_access_token: str, branch_name: str,
                 network_name: str, ansible_forks: Optional[int] = None, 
                 custom_inventory: Optional[List[str]] = None,
                 interval: Optional[int] = None,
                 node_type: Optional[NodeType] = None,
                 testnet_deploy_args: Optional[str] = None):
        super().__init__(owner, repo, id, personal_access_token, branch_name, name="Start Nodes")
        self.network_name = network_name
        self.ansible_forks = ansible_forks
        self.custom_inventory = custom_inventory
        self.interval = interval
        self.node_type = node_type
        self.testnet_deploy_args = testnet_deploy_args

    def get_workflow_inputs(self) -> Dict[str, Any]:
        """Get inputs specific to the start nodes workflow."""
        inputs = {
            "network-name": self.network_name,
        }
        
        if self.ansible_forks is not None:
            inputs["ansible-forks"] = str(self.ansible_forks)
        if self.custom_inventory is not None:
            inputs["custom-inventory"] = ",".join(self.custom_inventory)
        if self.interval is not None:
            inputs["interval"] = str(self.interval)
        if self.node_type is not None:
            inputs["node-type"] = self.node_type.value
        if self.testnet_deploy_args is not None and self.testnet_deploy_args.strip():
            inputs["testnet-deploy-args"] = self.testnet_deploy_args
            
        return inputs

class LaunchLegacyNetworkWorkflow(WorkflowRun):
    def __init__(self, owner: str, repo: str, id: int,
                 personal_access_token: str, branch_name: str, network_name: str,
                 config: Dict[str, Any]):
        super().__init__(owner, repo, id, personal_access_token, branch_name, name="Launch Legacy Network")
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
        for count_type in ["bootstrap-node-count", "generic-node-count", "private-node-count", "uploader-count"]:
            if count_type in self.config:
                node_counts.append(str(self.config[count_type]))
                
        vm_counts = []
        for count_type in ["bootstrap-vm-count", "generic-vm-count", "private-vm-count", 
                          "client-vm-count"]:
            if count_type in self.config:
                vm_counts.append(str(self.config[count_type]))
                
        if node_counts and vm_counts:
            inputs["node-vm-counts"] = f"({', '.join(node_counts)}), ({', '.join(vm_counts)})"

        deploy_args = []
        deploy_arg_mappings = {
            "bootstrap-node-vm-size": "--bootstrap-node-vm-size",
            "branch": "--branch",
            "chunk-size": "--chunk-size",
            "client-vm-size": "--client-vm-size",
            "evm-network-type": "--evm-network-type",
            "evm-data-payments-address": "--evm-data-payments-address",
            "evm-node-vm-size": "--evm-node-vm-size",
            "evm-payment-token-address": "--evm-payment-token-address",
            "evm-rpc-url": "--evm-rpc-url",
            "interval": "--interval",
            "max-archived-log-files": "--max-archived-log-files",
            "max-log-files": "--max-log-files",
            "node-vm-size": "--node-vm-size",
            "public-rpc": "--public-rpc",
            "region": "--region",
            "repo-owner": "--repo-owner",
            "rewards-address": "--rewards-address"
        }
        
        for config_key, arg_name in deploy_arg_mappings.items():
            if config_key in self.config:
                value = self.config[config_key]
                if isinstance(value, bool):
                    if value:
                        deploy_args.append(arg_name)
                else:
                    deploy_args.append(f"{arg_name} {value}")

        if "safenode-features" in self.config:
            features = self.config["safenode-features"]
            if isinstance(features, list):
                features_str = ",".join(features)
                deploy_args.append(f"--safenode-features {features_str}")
            else:
                deploy_args.append(f"--safenode-features {features}")
        
        if deploy_args:
            inputs["deploy-args"] = " ".join(deploy_args)

        if "environment-vars" in self.config:
            inputs["environment-vars"] = self.config["environment-vars"]

        testnet_deploy_args = self._build_testnet_deploy_args(self.config)
        if testnet_deploy_args:
            inputs["testnet-deploy-args"] = testnet_deploy_args

        return inputs

class NetworkStatusWorkflow(WorkflowRun):
    def __init__(self, owner: str, repo: str, id: int, 
                 personal_access_token: str, branch_name: str,
                 network_name: str, ansible_forks: Optional[int] = None,
                 testnet_deploy_args: Optional[str] = None):
        super().__init__(owner, repo, id, personal_access_token, branch_name, name="Network Status")
        self.network_name = network_name
        self.ansible_forks = ansible_forks
        self.testnet_deploy_args = testnet_deploy_args

    def get_workflow_inputs(self) -> Dict[str, Any]:
        """Get inputs specific to the network status workflow."""
        inputs = {
            "network-name": self.network_name,
        }
        
        if self.ansible_forks is not None:
            inputs["ansible-forks"] = str(self.ansible_forks)
        if self.testnet_deploy_args is not None and self.testnet_deploy_args.strip():
            inputs["testnet-deploy-args"] = self.testnet_deploy_args
            
        return inputs

class StartUploadersWorkflow(WorkflowRun):
    def __init__(self, owner: str, repo: str, id: int,
                 personal_access_token: str, branch_name: str,
                 network_name: str, testnet_deploy_args: Optional[str] = None):
        super().__init__(owner, repo, id, personal_access_token, branch_name, name="Start Uploaders")
        self.network_name = network_name
        self.testnet_deploy_args = testnet_deploy_args

    def get_workflow_inputs(self) -> Dict[str, Any]:
        """Get inputs specific to the start uploaders workflow."""
        inputs = {
            "network-name": self.network_name,
        }
        
        if self.testnet_deploy_args is not None and self.testnet_deploy_args.strip():
            inputs["testnet-deploy-args"] = self.testnet_deploy_args
            
        return inputs

class StopUploadersWorkflow(WorkflowRun):
    """Workflow for stopping uploaders on testnet nodes."""
    def __init__(
        self,
        owner: str,
        repo: str,
        id: int,
        personal_access_token: str,
        branch_name: str,
        network_name: str,
        testnet_deploy_args: Optional[str] = None
    ):
        super().__init__(owner, repo, id, personal_access_token, branch_name, name="Stop Uploaders")
        self.network_name = network_name
        self.testnet_deploy_args = testnet_deploy_args

    def get_workflow_inputs(self) -> Dict[str, Any]:
        """Get the inputs for the workflow."""
        inputs = {
            "network-name": self.network_name
        }
        
        if self.testnet_deploy_args:
            inputs["testnet-deploy-args"] = self.testnet_deploy_args
            
        return inputs

class DrainFundsWorkflow(WorkflowRun):
    def __init__(self, owner: str, repo: str, id: int,
                 personal_access_token: str, branch_name: str,
                 network_name: str, to_address: Optional[str] = None,
                 testnet_deploy_args: Optional[str] = None):
        super().__init__(owner, repo, id, personal_access_token, branch_name, name="Drain Funds")
        self.network_name = network_name
        self.to_address = to_address
        self.testnet_deploy_args = testnet_deploy_args

    def get_workflow_inputs(self) -> Dict[str, Any]:
        """Get inputs specific to the drain funds workflow."""
        inputs = {
            "network-name": self.network_name,
        }
        
        if self.to_address is not None:
            inputs["to-address"] = self.to_address
        if self.testnet_deploy_args is not None and self.testnet_deploy_args.strip():
            inputs["testnet-deploy-args"] = self.testnet_deploy_args
            
        return inputs

class BootstrapNetworkWorkflow(WorkflowRun):
    def __init__(self, owner: str, repo: str, id: int,
                 personal_access_token: str, branch_name: str, network_name: str,
                 environment_type: str, config: Dict[str, Any]):
        super().__init__(owner, repo, id, personal_access_token, branch_name, name="Bootstrap Network")
        self.network_name = network_name
        self.environment_type = environment_type
        self.config = config
        self._validate_config()

    def _validate_config(self) -> None:
        """Validate the configuration inputs."""
        required_fields = ["network-name", "environment-type", "rewards-address", "network-id"]
        for field in required_fields:
            if field not in self.config:
                raise KeyError(field)
                
        if "network-id" in self.config:
            network_id = self.config["network-id"]
            if not isinstance(network_id, int) or network_id < 1 or network_id > 255:
                raise ValueError("network-id must be an integer between 1 and 255")
                
        has_versions = any([
            "antnode-version" in self.config,
            "antctl-version" in self.config
        ])
        
        has_build_config = any([
            "branch" in self.config,
            "repo-owner" in self.config
        ])
        
        if has_versions and has_build_config:
            raise ValueError("Cannot specify both binary versions and build configuration")
            
        if has_build_config and ('branch' not in self.config or 'repo-owner' not in self.config):
            raise ValueError("Both branch and repo-owner must be specified for build configuration")

    def get_workflow_inputs(self) -> Dict[str, Any]:
        """Get inputs specific to the bootstrap network workflow."""
        inputs = {
            "network-name": self.config["network-name"],
            "environment-type": self.config["environment-type"],
            "network-id": str(self.config["network-id"])
        }

        if "peer" not in self.config and "network-contacts-url" not in self.config:
            raise ValueError("Either 'peer' or 'network-contacts-url' must be provided")
        
        if "peer" in self.config:
            inputs["peer"] = self.config["peer"]

        if all(key in self.config for key in ["antnode-version", "antctl-version"]):
            inputs["bin-versions"] = f"{self.config['antnode-version']},{self.config['antctl-version']}"

        node_counts = []
        for count_type in ["full-cone-private-node-count", "symmetric-private-node-count", "generic-node-count"]:
            if count_type in self.config:
                node_counts.append(str(self.config[count_type]))
                
        vm_counts = []
        for count_type in ["full-cone-private-vm-count", "symmetric-private-vm-count", "generic-vm-count"]:
            if count_type in self.config:
                vm_counts.append(str(self.config[count_type]))
                
        if node_counts and vm_counts:
            inputs["node-vm-counts"] = f"({', '.join(node_counts)}), ({', '.join(vm_counts)})"

        bootstrap_args = []
        bootstrap_arg_mappings = {
            "branch": "--branch",
            "chunk-size": "--chunk-size",
            "evm-network-type": "--evm-network-type",
            "evm-data-payments-address": "--evm-data-payments-address",
            "evm-payment-token-address": "--evm-payment-token-address",
            "evm-rpc-url": "--evm-rpc-url",
            "max-archived-log-files": "--max-archived-log-files",
            "max-log-files": "--max-log-files",
            "node-vm-size": "--node-vm-size",
            "region": "--region",
            "repo-owner": "--repo-owner",
            "rewards-address": "--rewards-address",
        }
        
        for config_key, arg_name in bootstrap_arg_mappings.items():
            if config_key in self.config:
                value = self.config[config_key]
                if isinstance(value, bool):
                    if value:
                        bootstrap_args.append(arg_name)
                else:
                    bootstrap_args.append(f"{arg_name} {value}")
        
        if "network-contacts-url" in self.config:
            bootstrap_args.append(f"--network-contacts-url {self.config['network-contacts-url']}")
        
        if bootstrap_args:
            inputs["bootstrap-args"] = " ".join(bootstrap_args)

        if "node-env" in self.config:
            inputs["node-env"] = self.config["node-env"]

        if "interval" in self.config:
            inputs["interval"] = str(self.config["interval"])

        testnet_deploy_args = self._build_testnet_deploy_args(self.config)
        if testnet_deploy_args:
            inputs["testnet-deploy-args"] = testnet_deploy_args

        return inputs

class ResetToNNodesWorkflow(WorkflowRun):
    def __init__(self, owner: str, repo: str, id: int,
                 personal_access_token: str, branch_name: str,
                 network_name: str, evm_network_type: str, node_count: str,
                 custom_inventory: Optional[List[str]] = None,
                 forks: Optional[int] = None,
                 node_type: Optional[NodeType] = None,
                 start_interval: Optional[int] = None,
                 stop_interval: Optional[int] = None,
                 version: Optional[str] = None,
                 testnet_deploy_args: Optional[str] = None):
        super().__init__(owner, repo, id, personal_access_token, branch_name, name="Reset to N Nodes")
        self.network_name = network_name
        self.evm_network_type = evm_network_type
        self.node_count = node_count
        self.custom_inventory = custom_inventory
        self.forks = forks
        self.node_type = node_type
        self.start_interval = start_interval
        self.stop_interval = stop_interval
        self.version = version
        self.testnet_deploy_args = testnet_deploy_args

    def get_workflow_inputs(self) -> Dict[str, Any]:
        """Get inputs specific to the reset to n nodes workflow."""
        inputs = {
            "network-name": self.network_name,
            "evm-network-type": self.evm_network_type,
            "node-count": self.node_count
        }
        
        if self.custom_inventory is not None:
            inputs["custom-inventory"] = ",".join(self.custom_inventory)
        if self.forks is not None:
            inputs["forks"] = str(self.forks)
        if self.node_type is not None:
            inputs["node-type"] = self.node_type.value
        if self.start_interval is not None:
            inputs["start-interval"] = str(self.start_interval)
        if self.stop_interval is not None:
            inputs["stop-interval"] = str(self.stop_interval)
        if self.version is not None:
            inputs["version"] = self.version
        if self.testnet_deploy_args is not None and self.testnet_deploy_args.strip():
            inputs["testnet-deploy-args"] = self.testnet_deploy_args
            
        return inputs

class TelegrafUpgradeClientConfigWorkflow(WorkflowRun):
    def __init__(self, owner: str, repo: str, id: int,
                 personal_access_token: str, branch_name: str,
                 network_name: str, ansible_forks: Optional[int] = None,
                 ansible_verbose: Optional[bool] = None,
                 testnet_deploy_args: Optional[str] = None):
        super().__init__(owner, repo, id, personal_access_token, branch_name, name="Telegraf -- Upgrade Client Config")
        self.network_name = network_name
        self.ansible_forks = ansible_forks
        self.ansible_verbose = ansible_verbose
        self.testnet_deploy_args = testnet_deploy_args

    def get_workflow_inputs(self) -> Dict[str, Any]:
        inputs = {
            "network-name": self.network_name,
        }
        
        if self.ansible_forks is not None:
            inputs["ansible-forks"] = str(self.ansible_forks)
        if self.ansible_verbose is not None:
            inputs["ansible-verbose"] = str(self.ansible_verbose).lower()
        if self.testnet_deploy_args is not None and self.testnet_deploy_args.strip():
            inputs["testnet-deploy-args"] = self.testnet_deploy_args
            
        return inputs

class TelegrafUpgradeGeoipConfigWorkflow(WorkflowRun):
    def __init__(self, owner: str, repo: str, id: int,
                 personal_access_token: str, branch_name: str,
                 network_name: str, ansible_forks: Optional[int] = None,
                 ansible_verbose: Optional[bool] = None,
                 testnet_deploy_args: Optional[str] = None):
        super().__init__(owner, repo, id, personal_access_token, branch_name, name="Telegraf -- Upgrade GeoIP Config")
        self.network_name = network_name
        self.ansible_forks = ansible_forks
        self.ansible_verbose = ansible_verbose
        self.testnet_deploy_args = testnet_deploy_args

    def get_workflow_inputs(self) -> Dict[str, Any]:
        inputs = {
            "network-name": self.network_name,
        }
        
        if self.ansible_forks is not None:
            inputs["ansible-forks"] = str(self.ansible_forks)
        if self.ansible_verbose is not None:
            inputs["ansible-verbose"] = str(self.ansible_verbose).lower()
        if self.testnet_deploy_args is not None and self.testnet_deploy_args.strip():
            inputs["testnet-deploy-args"] = self.testnet_deploy_args
            
        return inputs

class TelegrafUpgradeNodeConfigWorkflow(WorkflowRun):
    def __init__(self, owner: str, repo: str, id: int,
                 personal_access_token: str, branch_name: str,
                 network_name: str, ansible_forks: Optional[int] = None,
                 ansible_verbose: Optional[bool] = None,
                 testnet_deploy_args: Optional[str] = None):
        super().__init__(owner, repo, id, personal_access_token, branch_name, name="Telegraf -- Upgrade Node Config")
        self.network_name = network_name
        self.ansible_forks = ansible_forks
        self.ansible_verbose = ansible_verbose
        self.testnet_deploy_args = testnet_deploy_args

    def get_workflow_inputs(self) -> Dict[str, Any]:
        inputs = {
            "network-name": self.network_name,
        }
        
        if self.ansible_forks is not None:
            inputs["ansible-forks"] = str(self.ansible_forks)
        if self.ansible_verbose is not None:
            inputs["ansible-verbose"] = str(self.ansible_verbose).lower()
        if self.testnet_deploy_args is not None and self.testnet_deploy_args.strip():
            inputs["testnet-deploy-args"] = self.testnet_deploy_args
            
        return inputs

class StartDownloadersWorkflow(WorkflowRun):
    def __init__(self, owner: str, repo: str, id: int,
                 personal_access_token: str, branch_name: str,
                 network_name: str, testnet_deploy_args: Optional[str] = None):
        super().__init__(owner, repo, id, personal_access_token, branch_name, name="Start Downloaders")
        self.network_name = network_name
        self.testnet_deploy_args = testnet_deploy_args

    def get_workflow_inputs(self) -> Dict[str, Any]:
        inputs = {
            "network-name": self.network_name,
        }
        if self.testnet_deploy_args:
            inputs["testnet-deploy-args"] = self.testnet_deploy_args
        return inputs

class StopDownloadersWorkflow(WorkflowRun):
    def __init__(
        self,
        owner: str,
        repo: str,
        id: int,
        personal_access_token: str,
        branch_name: str,
        network_name: str,
        testnet_deploy_args: Optional[str] = None
    ):
        super().__init__(owner, repo, id, personal_access_token, branch_name, name="Stop Downloaders")
        self.network_name = network_name
        self.testnet_deploy_args = testnet_deploy_args

    def get_workflow_inputs(self) -> Dict[str, Any]:
        inputs = {
            "network-name": self.network_name,
        }
        
        if self.testnet_deploy_args:
            inputs["testnet-deploy_args"] = self.testnet_deploy_args
            
        return inputs

class NginxUpgradeConfigWorkflow(WorkflowRun):
    def __init__(self, owner: str, repo: str, id: int,
                 personal_access_token: str, branch_name: str,
                 network_name: str, ansible_forks: Optional[int] = None,
                 custom_inventory: Optional[List[str]] = None,
                 testnet_deploy_args: Optional[str] = None):
        super().__init__(owner, repo, id, personal_access_token, branch_name, name="Nginx -- Upgrade Config")
        self.network_name = network_name
        self.ansible_forks = ansible_forks
        self.custom_inventory = custom_inventory
        self.testnet_deploy_args = testnet_deploy_args

    def get_workflow_inputs(self) -> Dict[str, Any]:
        inputs = {
            "network-name": self.network_name,
        }
        
        if self.ansible_forks is not None:
            inputs["ansible-forks"] = str(self.ansible_forks)
        if self.custom_inventory is not None:
            inputs["custom-inventory"] = ",".join(self.custom_inventory)
        if self.testnet_deploy_args is not None and self.testnet_deploy_args.strip():
            inputs["testnet-deploy-args"] = self.testnet_deploy_args
            
        return inputs
