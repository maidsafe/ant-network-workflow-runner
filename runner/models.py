from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, Integer, String, DateTime, JSON, Boolean, ForeignKey, Enum as SqlEnum
from sqlalchemy.orm import relationship, mapped_column
from sqlalchemy.orm.collections import attribute_mapped_collection
from sqlalchemy.orm import backref
from .database import Base
from enum import Enum

class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id = Column(Integer, primary_key=True, index=True)
    workflow_name = Column(String, nullable=False)
    branch_name = Column(String, nullable=False)
    network_name = Column(String, nullable=False)
    triggered_at = Column(DateTime, nullable=False)
    inputs = Column(JSON, nullable=False)
    run_id = Column(Integer, nullable=False)

class DeploymentType(Enum):
    NETWORK = "network"
    CLIENT = "client"

class BaseDeployment(Base):
    __tablename__ = "base_deployments"

    id = Column(Integer, primary_key=True, index=True)
    deployment_type = Column(SqlEnum(DeploymentType), nullable=False)
    workflow_run_id = Column(Integer, ForeignKey("workflow_runs.id"), nullable=False)
    name = Column(String, nullable=False)
    triggered_at = Column(DateTime, nullable=False)
    run_id = Column(Integer, nullable=False)
    description = Column(String)
    region = Column(String, nullable=False, default="lon1")
    
    __mapper_args__ = {
        "polymorphic_on": deployment_type,
    }

class NetworkDeployment(BaseDeployment):
    __tablename__ = "network_deployments"

    id = Column(Integer, ForeignKey("base_deployments.id"), primary_key=True)
    ant_version = Column(String)
    antnode_version = Column(String)
    antctl_version = Column(String)
    branch = Column(String)
    repo_owner = Column(String)
    chunk_size = Column(Integer)
    antnode_features = Column(String)
    peer_cache_node_count = Column(Integer)
    generic_node_count = Column(Integer, nullable=False)
    private_node_count = Column(Integer)
    enable_downloaders = Column(Boolean)
    uploader_count = Column(Integer)
    peer_cache_vm_count = Column(Integer)
    generic_vm_count = Column(Integer, nullable=False)
    private_vm_count = Column(Integer)
    client_vm_count = Column(Integer)
    peer_cache_node_vm_size = Column(String)
    generic_node_vm_size = Column(String, nullable=False)
    private_node_vm_size = Column(String)
    client_vm_size = Column(String)
    evm_network_type = Column(String, nullable=False)
    rewards_address = Column(String, nullable=False)
    max_log_files = Column(Integer)
    max_archived_log_files = Column(Integer)
    evm_data_payments_address = Column(String)
    evm_payment_token_address = Column(String)
    evm_rpc_url = Column(String)
    related_pr = Column(Integer)
    network_id = Column(Integer)
    client_env = Column(String)
    node_env = Column(String)
    full_cone_private_node_count = Column(Integer)
    full_cone_private_vm_count = Column(Integer)
    full_cone_nat_gateway_vm_size = Column(String)
    symmetric_private_node_count = Column(Integer)
    symmetric_private_vm_count = Column(Integer)
    symmetric_nat_gateway_vm_size = Column(String)
    
    __mapper_args__ = {
        "polymorphic_identity": DeploymentType.NETWORK,
    }

class ClientDeployment(BaseDeployment):
    __tablename__ = "client_deployments"

    id = Column(Integer, ForeignKey("base_deployments.id"), primary_key=True)
    ant_version = Column(String)
    branch = Column(String)
    repo_owner = Column(String)
    chunk_size = Column(Integer)
    client_vm_count = Column(Integer, nullable=False, default=1)
    client_vm_size = Column(String, nullable=False, default="s-4vcpu-8gb")
    client_env = Column(String)
    evm_network_type = Column(String, nullable=False)
    evm_data_payments_address = Column(String)
    evm_payment_token_address = Column(String)
    evm_rpc_url = Column(String)
    network_id = Column(Integer)
    related_pr = Column(Integer)
    provider = Column(String, nullable=False, default="digital-ocean")
    wallet_secret_key = Column(String)
    environment_type = Column(String, nullable=False)
    disable_download_verifier = Column(Boolean, default=False)
    disable_performance_verifier = Column(Boolean, default=False)
    disable_random_verifier = Column(Boolean, default=False)
    disable_telegraf = Column(Boolean, default=False)
    disable_uploaders = Column(Boolean, default=False)
    expected_hash = Column(String)
    expected_size = Column(String)
    file_address = Column(String)
    initial_gas = Column(String)
    initial_tokens = Column(String)
    max_uploads = Column(Integer)
    network_contacts_url = Column(String)
    peer = Column(String)
    uploaders_count = Column(Integer, nullable=False, default=1)
    upload_size = Column(Integer, nullable=False, default=100)

    __mapper_args__ = {
        "polymorphic_identity": DeploymentType.CLIENT,
    }

class ComparisonDeployment(Base):
    __tablename__ = "comparison_deployments"

    id = Column(Integer, primary_key=True)
    comparison_id = Column(Integer, ForeignKey("comparisons.id"), nullable=False)
    deployment_id = Column(Integer, ForeignKey("base_deployments.id"), nullable=False)
    label = Column(String)
    
    comparison = relationship("Comparison", back_populates="test_deployments")
    deployment = relationship("BaseDeployment")

class Comparison(Base):
    __tablename__ = "comparisons"

    id = Column(Integer, primary_key=True, index=True)
    ref_id = Column(Integer, ForeignKey("base_deployments.id"), nullable=False)
    deployment_type = Column(SqlEnum(DeploymentType), nullable=False)
    description = Column(String)
    thread_link = Column(String)
    created_at = Column(DateTime, nullable=False)
    ref_label = Column(String)
    passed = Column(Boolean)

    ref_deployment = relationship("BaseDeployment", foreign_keys=[ref_id])
    test_deployments = relationship("ComparisonDeployment", back_populates="comparison")
    
    @property
    def test_environments(self):
        return [(cd.deployment, cd.label) for cd in self.test_deployments]

class ComparisonResult(Base):
    __tablename__ = "comparison_results"

    id = Column(Integer, primary_key=True, index=True)
    comparison_id = Column(Integer, ForeignKey("comparisons.id"), nullable=False)
    generic_nodes_report = Column(String)
    full_cone_nat_nodes_report = Column(String)
    symmetric_nat_nodes_report = Column(String)
    started_at = Column(DateTime, nullable=False)
    ended_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False)
    description = Column(String, nullable=False)

class ComparisonUploadResult(Base):
    __tablename__ = "comparison_upload_results"

    id = Column(Integer, primary_key=True, index=True)
    comparison_id = Column(Integer, ForeignKey("comparisons.id"), nullable=False)
    deployment_id = Column(Integer, ForeignKey("base_deployments.id"), nullable=False)
    env_name = Column(String, nullable=False)
    label = Column(String)
    total_uploaders = Column(Integer, nullable=False)
    successful_uploads = Column(Integer, nullable=False)
    records_uploaded = Column(Integer, nullable=False)
    avg_upload_time = Column(String, nullable=False)
    # The original error counts were unfortunately added as strings by the AI, but I didn't pick up on it.
    chunk_proof_error_count = Column(String, nullable=False)
    not_enough_quotes_error_count = Column(String, nullable=False)
    other_error_count = Column(String, nullable=False)
    payment_error_count = Column(Integer, nullable=True)
    put_record_quorum_error_count = Column(Integer, nullable=True)
    started_at = Column(DateTime, nullable=False)
    ended_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False)
    
    comparison = relationship("Comparison", backref="upload_results")
    deployment = relationship("BaseDeployment")

class ComparisonDownloadResult(Base):
    __tablename__ = "comparison_download_results"

    id = Column(Integer, primary_key=True, index=True)
    comparison_id = Column(Integer, ForeignKey("comparisons.id"), nullable=False)
    deployment_id = Column(Integer, ForeignKey("base_deployments.id"), nullable=False)
    env_name = Column(String, nullable=False)
    label = Column(String)
    standard_successful = Column(Integer, nullable=False)
    standard_errors = Column(Integer, nullable=False)
    standard_avg_time = Column(String, nullable=False)
    random_successful = Column(Integer, nullable=False)
    random_errors = Column(Integer, nullable=False)
    random_avg_time = Column(String, nullable=False)
    perf_successful = Column(Integer, nullable=False)
    perf_errors = Column(Integer, nullable=False)
    perf_avg_time = Column(String, nullable=False)
    started_at = Column(DateTime, nullable=False)
    ended_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False)
    
    comparison = relationship("Comparison", backref="download_results")
    deployment = relationship("BaseDeployment")

class SmokeTestResult(Base):
    __tablename__ = "smoke_test_results"

    id = Column(Integer, primary_key=True, index=True)
    deployment_id = Column(Integer, ForeignKey("base_deployments.id"), nullable=False)
    results = Column(JSON, nullable=False)
    created_at = Column(DateTime, nullable=False)

    deployment = relationship("BaseDeployment", backref="smoke_test_results")

class ClientSmokeTestResult(Base):
    __tablename__ = "client_smoke_test_results"

    id = Column(Integer, primary_key=True, index=True)
    deployment_id = Column(Integer, ForeignKey("client_deployments.id"), nullable=False)
    results = Column(JSON, nullable=False)
    created_at = Column(DateTime, nullable=False)

    deployment = relationship("ClientDeployment", backref="client_smoke_test_results")

@dataclass
class RecentDeployment:
    id: int
    name: str
    created_at: datetime

@dataclass
class ComparisonSummary:
    id: int
    title: str
    created_at: datetime
    thread_link: Optional[str]
    description: Optional[str]
    deployment_type: str