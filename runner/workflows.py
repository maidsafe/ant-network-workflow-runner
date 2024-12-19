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
        required_fields = ["network-name", "environment-type", "rewards-address", "network-id"]
        for field in required_fields:
            if field not in self.config:
                raise KeyError(field)
                
        if "network-id" in self.config:
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

        if all(key in self.config for key in ["ant-version", "antnode-version", "antctl-version"]):
            inputs["bin-versions"] = f"{self.config['ant-version']},{self.config['antnode-version']},{self.config['antctl-version']}"

        node_counts = []
        for count_type in ["peer-cache-node-count", "generic-node-count", "private-node-count", 
                          "downloader-count", "uploader-count"]:
            if count_type in self.config:
                node_counts.append(str(self.config[count_type]))
                
        vm_counts = []
        for count_type in ["peer-cache-vm-count", "generic-vm-count", "private-vm-count", 
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
            "evm-data-payments-address": "--evm-data-payments-address",
            "evm-node-vm-size": "--evm-node-vm-size",
            "evm-payment-token-address": "--evm-payment-token-address",
            "evm-rpc-url": "--evm-rpc-url",
            "interval": "--interval",
            "max-archived-log-files": "--max-archived-log-files",
            "max-log-files": "--max-log-files",
            "network-id": "--network-id",
            "node-vm-size": "--node-vm-size",
            "public-rpc": "--public-rpc",
            "repo-owner": "--repo-owner",
            "rewards-address": "--rewards-address",
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

        if "antnode-features" in self.config:
            features = self.config["antnode-features"]
            if isinstance(features, list):
                features_str = ",".join(features)
                deploy_args.append(f"--antnode-features {features_str}")
            else:
                deploy_args.append(f"--antnode-features {features}")
        
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

class UpscaleNetworkWorkflow(WorkflowRun):
    def __init__(self, owner: str, repo: str, id: int,
                 personal_access_token: str, branch_name: str,
                 network_name: str, desired_counts: str,
                 autonomi_version: Optional[str] = None,
                 safenode_version: Optional[str] = None,
                 safenode_manager_version: Optional[str] = None,
                 infra_only: Optional[bool] = None,
                 interval: Optional[int] = None,
                 plan: Optional[bool] = None,
                 testnet_deploy_repo_ref: Optional[str] = None):
        super().__init__(owner, repo, id, personal_access_token, branch_name, name="Upscale Network")
        self.network_name = network_name
        self.desired_counts = desired_counts
        self.autonomi_version = autonomi_version
        self.safenode_version = safenode_version
        self.safenode_manager_version = safenode_manager_version
        self.infra_only = infra_only
        self.interval = interval
        self.plan = plan
        self.testnet_deploy_repo_ref = testnet_deploy_repo_ref

    def get_workflow_inputs(self) -> Dict[str, Any]:
        """Get inputs specific to the upscale network workflow."""
        inputs = {
            "network-name": self.network_name,
            "desired-counts": self.desired_counts
        }
        
        if self.autonomi_version is not None:
            inputs["autonomi-version"] = self.autonomi_version
        if self.safenode_version is not None:
            inputs["safenode-version"] = self.safenode_version
        if self.safenode_manager_version is not None:
            inputs["safenode-manager-version"] = self.safenode_manager_version
        if self.infra_only is not None:
            inputs["infra-only"] = str(self.infra_only).lower()
        if self.interval is not None:
            inputs["interval"] = str(self.interval)
        if self.plan is not None:
            inputs["plan"] = str(self.plan).lower()
        if self.testnet_deploy_repo_ref is not None:
            inputs["testnet-deploy-repo-ref"] = self.testnet_deploy_repo_ref
            
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
            "evm-data-payments-address": "--evm-data-payments-address",
            "evm-node-vm-size": "--evm-node-vm-size",
            "evm-payment-token-address": "--evm-payment-token-address",
            "evm-rpc-url": "--evm-rpc-url",
            "interval": "--interval",
            "max-archived-log-files": "--max-archived-log-files",
            "max-log-files": "--max-log-files",
            "node-vm-size": "--node-vm-size",
            "public-rpc": "--public-rpc",
            "repo-owner": "--repo-owner",
            "rewards-address": "--rewards-address",
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
