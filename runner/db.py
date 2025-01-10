from datetime import datetime, UTC
from typing import Any, Dict, Optional, TypeVar, Generic, Type
from .database import get_db
from .models import WorkflowRun, Deployment, Comparison, ComparisonSummary, ComparisonDeployment, SmokeTestResult, RecentDeployment
from sqlalchemy import select
from sqlalchemy.orm import aliased

T = TypeVar('T')

class BaseRepository(Generic[T]):
    def __init__(self, model: Type[T]):
        self.model = model
        self.db = next(get_db())
    
    def get_by_id(self, id: int) -> Optional[T]:
        return self.db.query(self.model).filter(self.model.id == id).first()
    
    def save(self, entity: T) -> None:
        try:
            if not entity.id:
                self.db.add(entity)
            else:
                existing = self.get_by_id(entity.id)
                if not existing:
                    raise ValueError(f"{self.model.__name__} with ID {entity.id} not found")
            
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
    
    def close(self):
        self.db.close()

class ComparisonRepository(BaseRepository[Comparison]):
    def __init__(self):
        super().__init__(Comparison)

    def create_comparison(
            self, ref_id: int, test_ids: list[tuple[int, Optional[str]]],
            ref_label: Optional[str] = None, description: Optional[str] = None) -> None:
        """Create a new comparison between multiple deployments.
        
        Args:
            ref_id: ID of the reference deployment
            test_ids: List of tuples containing (deployment_id, label) for test environments
            ref_label: Optional label for the reference deployment
            description: Optional description of the comparison
        """
        ref_deployment = self.db.query(Deployment).filter(Deployment.id == ref_id).first()
        if not ref_deployment:
            raise ValueError(f"Deployment with ID {ref_id} not found")
        
        for test_id, _ in test_ids:
            test_deployment = self.db.query(Deployment).filter(Deployment.id == test_id).first()
            if not test_deployment:
                raise ValueError(f"Deployment with ID {test_id} not found")

        comparison = Comparison(
            ref_deployment=ref_deployment,
            created_at=datetime.now(UTC),
            ref_label=ref_label,
            description=description
        )
        self.save(comparison)
        
        for test_id, label in test_ids:
            test_assoc = ComparisonDeployment(
                comparison=comparison,
                deployment_id=test_id,
                label=label
            )
            self.db.add(test_assoc)
        self.db.commit()
        self.close()

    def list_comparisons(self) -> list[ComparisonSummary]:
        try:
            stmt = (
                select(
                    Comparison.id,
                    Deployment.name.label('ref_name'),
                    Comparison.ref_label,
                    Comparison.thread_link,
                    Comparison.description,
                    Comparison.passed,
                    Comparison.created_at,
                )
                .join(Deployment, Comparison.ref_id == Deployment.id)
                .order_by(Comparison.created_at.asc())
            )
            
            results = self.db.execute(stmt).all()
            
            summaries = []
            for row in results:
                test_envs = (
                    self.db.query(Deployment.name, ComparisonDeployment.label)
                    .join(ComparisonDeployment, Deployment.id == ComparisonDeployment.deployment_id)
                    .filter(ComparisonDeployment.comparison_id == row.id)
                    .all()
                )

                title = f"{row.ref_name}"
                for _, label in test_envs:
                    title += f" vs {label}"
                
                summaries.append(ComparisonSummary(
                    id=row.id,
                    title=title,
                    thread_link=row.thread_link,
                    description=row.description,
                    created_at=row.created_at,
                ))
                
            return summaries
        finally:
            self.db.close()

class DeploymentRepository(BaseRepository[Deployment]):
    def __init__(self):
        super().__init__(Deployment)

    def list_deployments(self) -> list[Deployment]:
        """
        Retrieve all deployments from the database using SQLAlchemy.
        
        Returns:
            List of Deployment objects ordered by triggered_at ascending
        """
        try:
            return (
                self.db.query(Deployment)
                .join(WorkflowRun, Deployment.workflow_run_id == WorkflowRun.run_id)
                .order_by(WorkflowRun.triggered_at.asc())
                .all()
            )
        finally:
            self.db.close()

    def record_deployment(
            self, workflow_run_id: int, config: Dict[str, Any], defaults: Dict[str, Any],
            is_legacy: bool = False, is_bootstrap: bool = False) -> None:
        """
        Record a deployment in the database using SQLAlchemy.
        
        Args:
            workflow_run_id: ID of the associated workflow run
            config: Dictionary containing deployment configuration
            defaults: Dictionary containing default values for the environment type
            is_legacy: Whether the deployment is a legacy deployment
            is_bootstrap: Whether the deployment is a bootstrap deployment
        """
        ant_version = config.get("autonomi-version" if is_legacy else "ant-version")
        antnode_version = config.get("safenode-version" if is_legacy else "antnode-version")
        antctl_version = config.get("safenode-manager-version" if is_legacy else "antctl-version")

        features = config.get("safenode-features" if is_legacy else "antnode-features")
        if isinstance(features, list):
            features = ",".join(features)
            
        if is_bootstrap:
            peer_cache_node_count = None
            peer_cache_vm_count = None
            peer_cache_node_vm_size = None
            downloader_count = None
            uploader_count = None
            uploader_vm_count = None
            uploader_vm_size = None
        else:
            peer_cache_node_count = config.get("peer-cache-node-count", defaults["peer_cache_node_count"])
            peer_cache_vm_count = config.get("peer-cache-vm-count", defaults["peer_cache_vm_count"])
            peer_cache_node_vm_size = config.get("peer-cache-node-vm-size", defaults["peer_cache_node_vm_size"])
            downloader_count = config.get("downloader-count", defaults["downloader_count"])
            uploader_count = config.get("uploader-count", defaults["uploader_count"])
            uploader_vm_count = config.get("uploader-vm-count", defaults["uploader_vm_count"])
            uploader_vm_size = config.get("uploader-vm-size", defaults["uploader_vm_size"])

        deployment = Deployment(
            workflow_run_id=workflow_run_id,
            name=config["network-name"],
            ant_version=ant_version,
            antnode_version=antnode_version,
            antctl_version=antctl_version,
            branch=config.get("branch"),
            repo_owner=config.get("repo-owner"),
            chunk_size=config.get("chunk-size"),
            antnode_features=features,
            peer_cache_node_count=peer_cache_node_count,
            generic_node_count=config.get("generic-node-count", defaults["generic_node_count"]),
            private_node_count=config.get("private-node-count", defaults["private_node_count"]),
            downloader_count=downloader_count,
            uploader_count=uploader_count,
            peer_cache_vm_count=peer_cache_vm_count,
            generic_vm_count=config.get("generic-vm-count", defaults["generic_vm_count"]),
            private_vm_count=config.get("private-vm-count", defaults["private_vm_count"]),
            uploader_vm_count=uploader_vm_count,
            peer_cache_node_vm_size=peer_cache_node_vm_size,
            generic_node_vm_size=config.get("node-vm-size", defaults["generic_node_vm_size"]),
            private_node_vm_size=config.get("node-vm-size", defaults["private_node_vm_size"]),
            uploader_vm_size=uploader_vm_size,
            evm_network_type=config.get("evm-network-type", "custom"),
            rewards_address=config["rewards-address"],
            max_log_files=config.get("max-log-files"),
            max_archived_log_files=config.get("max-archived-log-files"),
            evm_data_payments_address=config.get("evm-data-payments-address"),
            evm_payment_token_address=config.get("evm-payment-token-address"),
            evm_rpc_url=config.get("evm-rpc-url"),
            related_pr=config.get("related-pr"),
            network_id=config.get("network-id") if not is_legacy else None,
            triggered_at=datetime.now(UTC),
            run_id=workflow_run_id
        )
        self.save(deployment)

    def record_smoke_test_result(self, deployment_id: int, results: dict) -> None:
        """Record smoke test results for a deployment.
        
        Args:
            deployment_id: ID of the deployment
            results: Dictionary containing smoke test responses
        """
        deployment = self.get_by_id(deployment_id)
        if not deployment:
            raise ValueError(f"Deployment with ID {deployment_id} not found")
            
        smoke_test = SmokeTestResult(
            deployment_id=deployment_id,
            results=results,
            created_at=datetime.now(UTC)
        )
        self.db.add(smoke_test)
        self.db.commit()

    def get_smoke_test_result(self, deployment_id: int) -> Optional[SmokeTestResult]:
        return self.db.query(SmokeTestResult).filter(SmokeTestResult.deployment_id == deployment_id).first()

    def get_recent_deployments(self) -> list[RecentDeployment]:
        """Get the 10 most recent deployments.
        
        Returns:
            List of RecentDeployment view models, ordered by triggered_at descending
        """
        try:
            rows = list(
                self.db.query(
                    Deployment.id,
                    Deployment.name,
                    WorkflowRun.triggered_at
                )
                .join(WorkflowRun, Deployment.workflow_run_id == WorkflowRun.run_id)
                .order_by(WorkflowRun.triggered_at.desc())
                .limit(10)
                .all()
            )
            
            return [
                RecentDeployment(
                    id=row.id,
                    name=row.name,
                    created_at=row.triggered_at
                )
                for row in rows
            ]
        finally:
            self.db.close()

class WorkflowRunRepository(BaseRepository[WorkflowRun]):
    def __init__(self):
        super().__init__(WorkflowRun)

    def list_workflow_runs(self) -> list[WorkflowRun]:
        """
        Retrieve all workflow runs from the database.
        
        Returns:
            List of WorkflowRun model instances, ordered by triggered_at descending
        """
        try:
            return (
                self.db.query(WorkflowRun)
                .order_by(WorkflowRun.triggered_at.asc())
                .all()
            )
        finally:
            self.db.close()