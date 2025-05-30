from datetime import datetime, UTC
from typing import Any, Dict, Optional, TypeVar, Generic, Type
from .database import get_db
from .models import (
    ClientDeployment,
    ClientSmokeTestResult,
    Comparison,
    ComparisonDeployment,
    ComparisonResult,
    ComparisonSummary,
    ComparisonUploadResult,
    ComparisonDownloadResult,
    DeploymentType,
    RecentDeployment,
    SmokeTestResult,
    WorkflowRun,
    NetworkDeployment,
)
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
            ref_label: Optional[str] = None, description: Optional[str] = None,
            deployment_type: DeploymentType = DeploymentType.NETWORK) -> None:
        """Create a new comparison between multiple deployments.
        
        Args:
            ref_id: ID of the reference deployment
            test_ids: List of tuples containing (deployment_id, label) for test environments
            ref_label: Optional label for the reference deployment
            description: Optional description of the comparison
            deployment_type: Type of deployment (network or client)
        """
        if deployment_type == DeploymentType.NETWORK:
            deployment_model = NetworkDeployment
        else:
            deployment_model = ClientDeployment
        
        ref_deployment = self.db.query(deployment_model).filter(deployment_model.id == ref_id).first()
        if not ref_deployment:
            raise ValueError(f"{deployment_type.value} deployment with ID {ref_id} not found")
        
        for test_id, _ in test_ids:
            test_deployment = self.db.query(deployment_model).filter(deployment_model.id == test_id).first()
            if not test_deployment:
                raise ValueError(f"{deployment_type.value} deployment with ID {test_id} not found")

        comparison = Comparison(
            ref_deployment=ref_deployment,
            deployment_type=deployment_type,
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
            comparisons_stmt = (
                select(
                    Comparison.id,
                    Comparison.ref_id,
                    Comparison.deployment_type,
                    Comparison.ref_label,
                    Comparison.thread_link,
                    Comparison.description,
                    Comparison.passed,
                    Comparison.created_at,
                )
                .order_by(Comparison.created_at.asc())
            )
            
            comparisons_results = self.db.execute(comparisons_stmt).all()
            summaries = []
            
            for row in comparisons_results:
                deployment_type = row.deployment_type
                if deployment_type == DeploymentType.NETWORK:
                    deployment_model = NetworkDeployment
                else:
                    deployment_model = ClientDeployment
                    
                ref_deployment = self.db.query(deployment_model).filter(deployment_model.id == row.ref_id).first()
                if not ref_deployment:
                    continue
                    
                test_envs = (
                    self.db.query(deployment_model.name, ComparisonDeployment.label)
                    .join(ComparisonDeployment, deployment_model.id == ComparisonDeployment.deployment_id)
                    .filter(ComparisonDeployment.comparison_id == row.id)
                    .all()
                )

                title = ""
                for deployment, label in test_envs:
                    title += f"{label} [{deployment}] vs "
                title = title[:-4]
                title += f" vs {row.ref_label} [{ref_deployment.name}]"
                
                summaries.append(ComparisonSummary(
                    id=row.id,
                    title=title,
                    thread_link=row.thread_link,
                    description=row.description,
                    created_at=row.created_at,
                    deployment_type=deployment_type.value,
                ))
                
            return summaries
        finally:
            self.db.close()

class ComparisonResultRepository(BaseRepository[ComparisonResult]):
    def __init__(self):
        super().__init__(ComparisonResult)

    def get_results(self, comparison_id: int) -> Optional[ComparisonResult]:
        return self.db.query(ComparisonResult).filter(ComparisonResult.comparison_id == comparison_id).first()

class ComparisonUploadResultRepository(BaseRepository[ComparisonUploadResult]):
    def __init__(self):
        super().__init__(ComparisonUploadResult)

    def get_results_for_comparison(self, comparison_id: int) -> list[ComparisonUploadResult]:
        """Get all upload results for a specific comparison.
        
        Args:
            comparison_id: ID of the comparison
            
        Returns:
            List of ComparisonUploadResult instances
        """
        try:
            return (
                self.db.query(ComparisonUploadResult)
                .filter(ComparisonUploadResult.comparison_id == comparison_id)
                .all()
            )
        finally:
            self.db.close()

class ComparisonDownloadResultRepository(BaseRepository[ComparisonDownloadResult]):
    def __init__(self):
        super().__init__(ComparisonDownloadResult)

    def get_results_for_comparison(self, comparison_id: int) -> list[ComparisonDownloadResult]:
        """Get all download results for a specific comparison.
        
        Args:
            comparison_id: ID of the comparison
            
        Returns:
            List of ComparisonDownloadResult instances
        """
        try:
            return (
                self.db.query(ComparisonDownloadResult)
                .filter(ComparisonDownloadResult.comparison_id == comparison_id)
                .all()
            )
        finally:
            self.db.close()

class NetworkDeploymentRepository(BaseRepository[NetworkDeployment]):
    def __init__(self):
        super().__init__(NetworkDeployment)

    def list_deployments(self) -> list[NetworkDeployment]:
        """
        Retrieve all deployments from the database using SQLAlchemy.
        
        Returns:
            List of Deployment objects ordered by triggered_at ascending
        """
        try:
            return (
                self.db.query(NetworkDeployment)
                .join(WorkflowRun, NetworkDeployment.workflow_run_id == WorkflowRun.run_id)
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
            client_vm_count = None
            client_vm_size = None
            peer_cache_node_count = None
            peer_cache_vm_count = None
            peer_cache_node_vm_size = None
            enable_downloaders = None
            uploader_count = None
        else:
            client_vm_count = config.get("client-vm-count", defaults["client_vm_count"])
            client_vm_size = config.get("client-vm-size", defaults["client_vm_size"])
            peer_cache_node_count = config.get("peer-cache-node-count", defaults["peer_cache_node_count"])
            peer_cache_vm_count = config.get("peer-cache-vm-count", defaults["peer_cache_vm_count"])
            peer_cache_node_vm_size = config.get("peer-cache-node-vm-size", defaults["peer_cache_node_vm_size"])
            enable_downloaders = config.get("enable-downloaders", defaults["enable_downloaders"])
            uploader_count = config.get("uploader-count", defaults["uploader_count"])

        deployment = NetworkDeployment(
            workflow_run_id=workflow_run_id,
            name=config["network-name"],
            ant_version=ant_version,
            antnode_version=antnode_version,
            antctl_version=antctl_version,
            branch=config.get("branch"),
            client_vm_count=client_vm_count,
            client_vm_size=client_vm_size,
            repo_owner=config.get("repo-owner"),
            chunk_size=config.get("chunk-size"),
            antnode_features=features,
            peer_cache_node_count=peer_cache_node_count,
            generic_node_count=config.get("generic-node-count", defaults["generic_node_count"]),
            private_node_count=None,
            enable_downloaders=enable_downloaders,
            uploader_count=uploader_count,
            peer_cache_vm_count=peer_cache_vm_count,
            generic_vm_count=config.get("generic-vm-count", defaults["generic_vm_count"]),
            private_vm_count=None,
            peer_cache_node_vm_size=peer_cache_node_vm_size,
            generic_node_vm_size=config.get("node-vm-size", defaults["generic_node_vm_size"]),
            private_node_vm_size=None,
            evm_network_type=config.get("evm-network-type", "custom"),
            rewards_address=config["rewards-address"],
            max_log_files=config.get("max-log-files"),
            max_archived_log_files=config.get("max-archived-log-files"),
            evm_data_payments_address=config.get("evm-data-payments-address"),
            evm_payment_token_address=config.get("evm-payment-token-address"),
            evm_rpc_url=config.get("evm-rpc-url"),
            related_pr=config.get("related-pr"),
            network_id=config.get("network-id") if not is_legacy else None,
            description=config.get("description"),
            triggered_at=datetime.now(UTC),
            run_id=workflow_run_id,
            full_cone_private_node_count=config.get("full-cone-private-node-count", defaults["full_cone_private_node_count"]),
            full_cone_private_vm_count=config.get("full-cone-private-vm-count", defaults["full_cone_private_vm_count"]),
            full_cone_nat_gateway_vm_size=config.get("full-cone-nat-gateway-vm-size", defaults["full_cone_nat_gateway_vm_size"]),
            symmetric_private_node_count=config.get("symmetric-private-node-count", defaults["symmetric_private_node_count"]),
            symmetric_private_vm_count=config.get("symmetric-private-vm-count", defaults["symmetric_private_vm_count"]),
            symmetric_nat_gateway_vm_size=config.get("symmetric-nat-gateway-vm-size", defaults["symmetric_nat_gateway_vm_size"]),
            client_env=config.get("client-env"),
            node_env=config.get("node-env"),
            region=config.get("region", "lon1"),
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
                    NetworkDeployment.id,
                    NetworkDeployment.name,
                    WorkflowRun.triggered_at
                )
                .join(WorkflowRun, NetworkDeployment.workflow_run_id == WorkflowRun.run_id)
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

class ClientDeploymentRepository(BaseRepository[ClientDeployment]):
    def __init__(self):
        super().__init__(ClientDeployment)

    def list_client_deployments(self) -> list[ClientDeployment]:
        try:
            return self.db.query(self.model).order_by(self.model.triggered_at.asc()).all()
        finally:
            self.close()

    def record_client_deployment(self, workflow_run_id: int, config: Dict[str, Any]) -> None:
        """Record a client deployment in the database.
        
        Args:
            workflow_run_id: ID of the workflow run
            config: Configuration dictionary
        """
        workflow_run = self.db.query(WorkflowRun).filter(WorkflowRun.run_id == workflow_run_id).first()
        if not workflow_run:
            raise ValueError(f"Workflow run with ID {workflow_run_id} not found")
        
        deployment = ClientDeployment(
            workflow_run_id=workflow_run_id,
            name=config["network-name"],
            triggered_at=workflow_run.triggered_at,
            run_id=workflow_run.run_id,
            network_id=config.get("network-id"),
            environment_type=config["environment-type"],
            evm_network_type=config.get("evm-network-type", "arbitrum-one"),
            provider=config.get("provider", "digital-ocean"),
            ant_version=config.get("ant-version"),
            branch=config.get("branch"),
            repo_owner=config.get("repo-owner"),
            client_vm_count=config.get("client-vm-count"),
            client_vm_size=config.get("client-vm-size"),
            client_env=config.get("client-env"),
            evm_data_payments_address=config.get("evm-data-payments-address"),
            evm_payment_token_address=config.get("evm-payment-token-address"),
            evm_rpc_url=config.get("evm-rpc-url"),
            description=config.get("description"),
            region=config.get("region"),
            wallet_secret_key=config.get("wallet-secret-key"),
            chunk_size=config.get("chunk-size"),
            disable_download_verifier=config.get("disable-download-verifier"),
            disable_performance_verifier=config.get("disable-performance-verifier"),
            disable_random_verifier=config.get("disable-random-verifier"),
            disable_telegraf=config.get("disable-telegraf"),
            disable_uploaders=config.get("disable-uploaders"),
            expected_hash=config.get("expected-hash"),
            expected_size=config.get("expected-size"),
            file_address=config.get("file-address"),
            initial_gas=config.get("initial-gas"),
            initial_tokens=config.get("initial-tokens"),
            max_uploads=config.get("max-uploads"),
            network_contacts_url=config.get("network-contacts-url"),
            peer=config.get("peer"),
            uploaders_count=config.get("uploaders-count"),
            upload_size=config.get("upload-size")
        )
        
        self.save(deployment)
        self.close()

    def record_smoke_test_result(self, deployment_id: int, results: dict) -> None:
        """Record smoke test results for a deployment.
        
        Args:
            deployment_id: ID of the deployment
            results: Dictionary containing smoke test responses
        """
        deployment = self.get_by_id(deployment_id)
        if not deployment:
            raise ValueError(f"Client deployment with ID {deployment_id} not found")
            
        smoke_test = ClientSmokeTestResult(
            deployment_id=deployment_id,
            results=results,
            created_at=datetime.now(UTC)
        )
        self.db.add(smoke_test)
        self.db.commit()

    def get_smoke_test_result(self, deployment_id: int) -> Optional[ClientSmokeTestResult]:
        return self.db.query(ClientSmokeTestResult).filter(ClientSmokeTestResult.deployment_id == deployment_id).first()

    def get_recent_deployments(self) -> list[RecentDeployment]:
        """Get the 10 most recent deployments.
        
        Returns:
            List of RecentDeployment view models, ordered by triggered_at descending
        """
        try:
            rows = list(
                self.db.query(
                    ClientDeployment.id,
                    ClientDeployment.name,
                    WorkflowRun.triggered_at
                )
                .join(WorkflowRun, ClientDeployment.workflow_run_id == WorkflowRun.run_id)
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