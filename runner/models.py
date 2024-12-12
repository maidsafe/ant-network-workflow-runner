from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class Deployment:
    id: int
    name: str
    ant_version: Optional[str]
    antnode_version: Optional[str]
    antctl_version: Optional[str]
    branch: Optional[str]
    repo_owner: Optional[str]
    chunk_size: Optional[int]
    antnode_features: Optional[str]
    peer_cache_node_count: int
    generic_node_count: int
    private_node_count: int
    downloader_count: int
    uploader_count: int
    peer_cache_vm_count: int
    generic_vm_count: int
    private_vm_count: int
    uploader_vm_count: int
    peer_cache_node_vm_size: str
    generic_node_vm_size: str
    private_node_vm_size: str
    uploader_vm_size: str
    evm_network_type: str
    rewards_address: str
    max_log_files: Optional[int]
    max_archived_log_files: Optional[int]
    evm_data_payments_address: Optional[str]
    evm_payment_token_address: Optional[str]
    evm_rpc_url: Optional[str]
    related_pr: Optional[int]
    network_id: Optional[int]
    triggered_at: datetime
    run_id: int

@dataclass
class Comparison:
    id: int
    test_deployment: Deployment
    ref_deployment: Deployment
    thread_link: Optional[str]
    created_at: datetime
    report: Optional[str]
    result_recorded_at: Optional[datetime]
    started_at: Optional[datetime]
    ended_at: Optional[datetime]
    ref_version: Optional[str]
    test_version: Optional[str]
    passed: Optional[bool] 

@dataclass
class ComparisonSummary:
    id: int
    test_name: str
    ref_name: str
    thread_link: Optional[str]
    passed: Optional[bool]
    created_at: datetime
    result_recorded_at: Optional[datetime] 