from typing import List
from runner.models import ClientDeployment, Deployment

REPO_OWNER = "maidsafe"
REPO_NAME = "sn-testnet-workflows"
AUTONOMI_REPO_NAME = "autonomi"

def build_deployment_report(deployment: Deployment) -> List[str]:
    """Build a detailed report about a specific deployment.
    
    Args:
        deployment: The deployment to format
        
    Returns:
        List[str]: Lines of formatted deployment details
    """
    lines = []
    lines.append(f"Deployed: {deployment.triggered_at.strftime('%Y-%m-%d %H:%M:%S')}")
    
    evm_type_display = {
        "anvil": "Anvil",
        "arbitrum-one": "Arbitrum One",
        "arbitrum-sepolia": "Arbitrum Sepolia", 
        "custom": "Custom"
    }.get(deployment.evm_network_type, deployment.evm_network_type)
    
    lines.append(f"EVM Type: {evm_type_display}")
    lines.append(f"Workflow run: https://github.com/{REPO_OWNER}/{REPO_NAME}/actions/runs/{deployment.run_id}")
    
    if deployment.related_pr:
        lines.append(f"Related PR: #{deployment.related_pr}")
        lines.append(f"Link: https://github.com/{REPO_OWNER}/{AUTONOMI_REPO_NAME}/pull/{deployment.related_pr}")

    if deployment.ant_version:
        lines.append(f"===============")
        lines.append(f"Version Details")
        lines.append(f"===============")
        lines.append(f"Ant: {deployment.ant_version}")
        lines.append(f"Antnode: {deployment.antnode_version}")
        lines.append(f"Antctl: {deployment.antctl_version}")

    if deployment.branch:
        lines.append(f"=====================")
        lines.append(f"Custom Branch Details")
        lines.append(f"=====================")
        lines.append(f"Branch: {deployment.branch}")
        lines.append(f"Repo Owner: {deployment.repo_owner}")
        lines.append(f"Link: https://github.com/{deployment.repo_owner}/{AUTONOMI_REPO_NAME}/tree/{deployment.branch}")
        if deployment.chunk_size:
            lines.append(f"Chunk Size: {deployment.chunk_size}")
        if deployment.antnode_features:
            lines.append(f"Antnode Features: {deployment.antnode_features}")

    lines.append(f"==================")
    lines.append(f"Node Configuration")
    lines.append(f"==================")
    lines.append(f"Peer cache nodes: {deployment.peer_cache_vm_count}x{deployment.peer_cache_node_count} [{deployment.peer_cache_node_vm_size}]")
    lines.append(f"Generic nodes: {deployment.generic_vm_count}x{deployment.generic_node_count} [{deployment.generic_node_vm_size}]")
    lines.append(f"Full cone private nodes: {deployment.full_cone_private_vm_count}x{deployment.full_cone_private_node_count} [{deployment.generic_node_vm_size}]")
    lines.append(f"Symmetric private nodes: {deployment.symmetric_private_vm_count}x{deployment.symmetric_private_node_count} [{deployment.generic_node_vm_size}]")
    total_nodes = deployment.generic_vm_count * deployment.generic_node_count
    if deployment.peer_cache_vm_count and deployment.peer_cache_node_count:
        total_nodes += deployment.peer_cache_vm_count * deployment.peer_cache_node_count
    if deployment.full_cone_private_vm_count and deployment.full_cone_private_node_count:
        total_nodes += deployment.full_cone_private_vm_count * deployment.full_cone_private_node_count
    if deployment.symmetric_private_vm_count and deployment.symmetric_private_node_count:
        total_nodes += deployment.symmetric_private_vm_count * deployment.symmetric_private_node_count
    lines.append(f"Total: {total_nodes}")

    lines.append(f"====================")
    lines.append(f"Client Configuration")
    lines.append(f"====================")
    lines.append(f"{deployment.client_vm_count}x{deployment.uploader_count} [{deployment.client_vm_size}]")
    total_uploaders = deployment.client_vm_count * deployment.uploader_count
    lines.append(f"Total: {total_uploaders}")

    if deployment.max_log_files or deployment.max_archived_log_files or deployment.client_env or deployment.node_env:
        lines.append(f"==================")
        lines.append(f"Misc Configuration")
        lines.append(f"==================")
        if deployment.client_env:
            lines.append(f"Client vars: {deployment.client_env}")
        if deployment.max_log_files:
            lines.append(f"Max log files: {deployment.max_log_files}")
        if deployment.max_archived_log_files:
            lines.append(f"Max archived log files: {deployment.max_archived_log_files}")
        if deployment.node_env:
            lines.append(f"Node vars: {deployment.node_env}")
        
    if any([deployment.evm_data_payments_address, 
            deployment.evm_payment_token_address, 
            deployment.evm_rpc_url]):
        lines.append(f"=================")
        lines.append(f"EVM Configuration")
        lines.append(f"=================")
        if deployment.evm_data_payments_address:
            lines.append(f"Data Payments Address: {deployment.evm_data_payments_address}")
        if deployment.evm_payment_token_address:
            lines.append(f"Payment Token Address: {deployment.evm_payment_token_address}")
        if deployment.evm_rpc_url:
            lines.append(f"RPC URL: {deployment.evm_rpc_url}")
            
    return lines

def build_client_deployment_report(deployment: ClientDeployment) -> List[str]:
    """Build a detailed report about a specific client deployment.
    
    Args:
        deployment: The deployment to format
        
    Returns:
        List[str]: Lines of formatted deployment details
    """
    timestamp = deployment.triggered_at.strftime("%Y-%m-%d %H:%M:%S")
    lines = []

    lines.append(f"Deployed: {timestamp}")
    lines.append(f"Region: {deployment.region}")
    lines.append(f"Environment Type: {deployment.environment_type}")
    lines.append(f"Workflow run: https://github.com/{REPO_OWNER}/{REPO_NAME}/actions/runs/{deployment.run_id}")
    if deployment.related_pr:
        lines.append(f"Related PR: #{deployment.related_pr}")
        lines.append(f"Link: https://github.com/{REPO_OWNER}/{AUTONOMI_REPO_NAME}/pull/{deployment.related_pr}")

    if deployment.ant_version:
        lines.append("")
        lines.append(f"===============")
        lines.append(f"Version Details")
        lines.append(f"===============")
        lines.append(f"Ant: {deployment.ant_version}")

    if deployment.branch:
        lines.append("")
        lines.append(f"=====================")
        lines.append(f"Custom Branch Details")
        lines.append(f"=====================")
        lines.append(f"Branch: {deployment.branch}")
        lines.append(f"Repo Owner: {deployment.repo_owner}")
        lines.append(f"Link: https://github.com/{deployment.repo_owner}/{AUTONOMI_REPO_NAME}/tree/{deployment.branch}")
        if deployment.chunk_size:
            lines.append(f"Chunk Size: {deployment.chunk_size}")

    lines.append("")
    lines.append(f"====================")
    lines.append(f"Client Configuration")
    lines.append(f"====================")
    lines.append(f"VMs: {deployment.client_vm_count} [{deployment.client_vm_size}]")
    if deployment.disable_uploaders:
        lines.append(f"Uploaders: disabled")
    else:
        lines.append(f"Uploaders: {deployment.uploaders_count}")
    if deployment.disable_download_verifier:
        lines.append(f"Download verifier: disabled")
    else:
        lines.append(f"Download verifier: running")
    if deployment.disable_performance_verifier:
        lines.append(f"Performance download verifier: disabled")
    elif deployment.file_address:
        lines.append(f"Performance download verifier: single file mode")
        lines.append(f"  - Address: {deployment.file_address}")
        lines.append(f"  - Expected hash: {deployment.expected_hash}")
        lines.append(f"  - Expected size: {deployment.expected_size}")
    else:
        lines.append(f"Performance download verifier: running")
    if deployment.disable_random_verifier:
        lines.append(f"Random download verifier: disabled")
    else:
        lines.append(f"Random download verifier: running")
    if deployment.network_id != 1 and deployment.network_id != 2:
        lines.append(f"Running against production network")
    else:
        if deployment.network_contacts_url:
            lines.append(f"Network Contacts URL: {deployment.network_contacts_url}")
        if deployment.peer:
            lines.append(f"Peer: {deployment.peer}")
        
    lines.append("")
    lines.append(f"=================")
    lines.append(f"EVM Configuration")
    lines.append(f"=================")
    evm_type_display = {
        "anvil": "Anvil",
        "arbitrum-one": "Arbitrum One",
        "arbitrum-sepolia": "Arbitrum Sepolia", 
        "custom": "Custom"
    }.get(deployment.evm_network_type, deployment.evm_network_type)
    lines.append(f"Type: {evm_type_display}")
    if deployment.evm_data_payments_address:
        lines.append(f"Data Payments Address: {deployment.evm_data_payments_address}")
    if deployment.evm_payment_token_address:
        lines.append(f"Payment Token Address: {deployment.evm_payment_token_address}")
    if deployment.evm_rpc_url:
        lines.append(f"RPC URL: {deployment.evm_rpc_url}")
    if deployment.initial_gas:
        lines.append(f"Initial Gas: {deployment.initial_gas}")
    if deployment.initial_tokens:
        lines.append(f"Initial Tokens: {deployment.initial_tokens}")

    return lines