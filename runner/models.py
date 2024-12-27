from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, Integer, String, DateTime, JSON, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base

class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id = Column(Integer, primary_key=True, index=True)
    workflow_name = Column(String, nullable=False)
    branch_name = Column(String, nullable=False)
    network_name = Column(String, nullable=False)
    triggered_at = Column(DateTime, nullable=False)
    inputs = Column(JSON, nullable=False)
    run_id = Column(Integer, nullable=False)

class Deployment(Base):
    __tablename__ = "deployments"

    id = Column(Integer, primary_key=True, index=True)
    workflow_run_id = Column(Integer, ForeignKey("workflow_runs.id"), nullable=False)
    name = Column(String, nullable=False)
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
    downloader_count = Column(Integer)
    uploader_count = Column(Integer)
    peer_cache_vm_count = Column(Integer)
    generic_vm_count = Column(Integer, nullable=False)
    private_vm_count = Column(Integer)
    uploader_vm_count = Column(Integer)
    peer_cache_node_vm_size = Column(String)
    generic_node_vm_size = Column(String, nullable=False)
    private_node_vm_size = Column(String)
    uploader_vm_size = Column(String)
    evm_network_type = Column(String, nullable=False)
    rewards_address = Column(String, nullable=False)
    max_log_files = Column(Integer)
    max_archived_log_files = Column(Integer)
    evm_data_payments_address = Column(String)
    evm_payment_token_address = Column(String)
    evm_rpc_url = Column(String)
    related_pr = Column(Integer)
    network_id = Column(Integer)
    triggered_at = Column(DateTime, nullable=False)
    run_id = Column(Integer, nullable=False)

class Comparison(Base):
    __tablename__ = "comparisons"

    id = Column(Integer, primary_key=True, index=True)
    test_id = Column(Integer, ForeignKey("deployments.id"), nullable=False)
    ref_id = Column(Integer, ForeignKey("deployments.id"), nullable=False)
    thread_link = Column(String)
    created_at = Column(DateTime, nullable=False)
    report = Column(String)
    result_recorded_at = Column(DateTime)
    started_at = Column(DateTime)
    ended_at = Column(DateTime)
    ref_version = Column(String)
    test_version = Column(String)
    passed = Column(Boolean)

    test_deployment = relationship("Deployment", foreign_keys=[test_id])
    ref_deployment = relationship("Deployment", foreign_keys=[ref_id])

@dataclass
class ComparisonSummary:
    id: int
    test_name: str
    ref_name: str
    thread_link: Optional[str]
    passed: Optional[bool]
    created_at: datetime
    result_recorded_at: Optional[datetime] 