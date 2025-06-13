import os
import sys
import toml
from pathlib import Path
from typing import List, Optional

from runner.github import (
    get_breaking_prs,
    get_merged_prs_by_author,
    read_pr_numbers,
)
from runner.linear import (
    Team,
    create_issue,
    create_project,
    create_project_update,
    get_in_progress_state_id,
    get_projects,
    get_qa_label_id,
)

def get_binary_versions(autonomi_repo_path: str) -> tuple[str, dict[str, str]]:
    """Get binary versions from the autonomi repository.
    
    Args:
        autonomi_repo_path: Path to the autonomi repository
        
    Returns:
        A tuple containing:
        - Formatted string with binary versions
        - Dictionary mapping binary names to their versions
        
    Raises:
        FileNotFoundError: If Cargo.toml files are not found
        ValueError: If versions cannot be read from Cargo.toml files
    """
    crate_binary_map = {
        "ant-node": "antnode",
        "ant-node-manager": ["antctl", "antctld"],
        "ant-cli": "ant",
        "nat-detection": "nat-detection",
        "node-launchpad": "node-launchpad"
    }
    
    repo_path = Path(autonomi_repo_path)
    if not repo_path.exists():
        raise FileNotFoundError(f"Autonomi repository path does not exist: {autonomi_repo_path}")
    
    markdown_lines = ["## Binary Versions\n"]
    binary_versions_dict = {}
    
    for crate, binaries in crate_binary_map.items():
        cargo_toml_path = repo_path / crate / "Cargo.toml"
        if not cargo_toml_path.exists():
            raise FileNotFoundError(f"Cargo.toml not found for crate {crate} at {cargo_toml_path}")
        
        with open(cargo_toml_path, 'r') as f:
            cargo_toml = toml.load(f)
        
        version = cargo_toml.get('package', {}).get('version')
        if not version:
            raise ValueError(f"Version not found in Cargo.toml for crate {crate}")
        
        if isinstance(binaries, list):
            for binary in binaries:
                markdown_lines.append(f"* `{binary}`: v{version}")
                binary_versions_dict[binary] = version
        else:
            markdown_lines.append(f"* `{binaries}`: v{version}")
            binary_versions_dict[binaries] = version
    
    return "\n".join(markdown_lines), binary_versions_dict

def new(path: str, package_version: str, autonomi_repo_path: Optional[str] = None):
    """Create a new release project in Linear.
    
    Args:
        path: Path to a file containing PR numbers, one per line
        package_version: The package version for the release
        autonomi_repo_path: Optional path to the autonomi repository. If not provided,
                           will read from ANT_RUNNER_AUTONOMI_REPO_PATH environment variable
        
    Raises:
        ValueError: If a project with the version already exists
        FileNotFoundError: If autonomi repository path is not found
    """
    try:
        if autonomi_repo_path is None:
            autonomi_repo_path = os.getenv("ANT_RUNNER_AUTONOMI_REPO_PATH")
            if not autonomi_repo_path:
                raise ValueError("autonomi_repo_path not provided and ANT_RUNNER_AUTONOMI_REPO_PATH environment variable not set")
        
        with open(path, "r") as file:
            pr_numbers = [int(line.strip()) for line in file if line.strip()]
        
        if not pr_numbers:
            print(f"Error: No PR numbers found in file {path}")
            sys.exit(1)
        
        binary_versions_markdown, binary_versions = get_binary_versions(autonomi_repo_path)
        binary_versions_markdown += "\n\n These will proceed from RC to full versions."
        prs_by_author = get_merged_prs_by_author(pr_numbers)
        
        projects = get_projects(Team.Releases)
        
        existing_project = next((p for p in projects if p["name"] == package_version), None)
        if existing_project:
            raise ValueError(f"Project for version {package_version} already exists")

        checklist = f"""## Staging Tests

- [ ] Environment comparison to evaluate standard metrics for improvements and regressions
- [ ] Upscale environment from 425 to 1975 generic nodes to ensure no regressions on open connections
- [ ] Upscale environment from 25 to 475 symmetric NAT nodes to ensure no regressions on open connections
- [ ] Backwards compatibility: bootstrap {package_version} to network with previous version and observe metrics to ensure communication
- [ ] Backwards compatibility: upgrade various older node versions to {package_version}
- [ ] Mainnet client comparison to evaluate uploads/downloads for improvements and regressions"""

        content = f"{checklist}\n\n{binary_versions_markdown}\n\n## Merged Pull Requests\n\n{prs_by_author}"
        project_id = create_project(
            f"Release {package_version}", "Full feature release from `main`", content, Team.Releases)
        
        qa_label_id = get_qa_label_id(Team.QA)
        in_progress_state_id = get_in_progress_state_id(Team.QA)

        create_issue(
            f"Produce the release candidate", 
            None, 
            Team.Releases, 
            project_id, 
            [qa_label_id], 
            in_progress_state_id, 
        )
        create_issue(
            f"Produce release changelog", 
            None, 
            Team.Releases, 
            project_id, 
            [qa_label_id], 
            in_progress_state_id, 
        )
        create_issue(
            f"Setup the environment comparison test", 
            None, 
            Team.Releases, 
            project_id, 
            [qa_label_id], 
            in_progress_state_id, 
        )
        create_issue(
            f"Setup the generic node upscaling test", 
            None, 
            Team.Releases, 
            project_id, 
            [qa_label_id], 
            in_progress_state_id, 
        )
        create_issue(
            f"Setup the symmetric NAT node upscaling test", 
            None, 
            Team.Releases, 
            project_id, 
            [qa_label_id], 
            in_progress_state_id, 
        )
        create_issue(
            f"Setup the basic backwards compatibility test", 
            None, 
            Team.Releases, 
            project_id, 
            [qa_label_id], 
            in_progress_state_id, 
        )
        create_issue(
            f"Setup the comprehensive backwards compatibility test", 
            None, 
            Team.Releases, 
            project_id, 
            [qa_label_id], 
            in_progress_state_id, 
        )
        create_issue(
            f"Setup the mainnet client comparison test", 
            None, 
            Team.Releases, 
            project_id, 
            [qa_label_id], 
            in_progress_state_id, 
        )

        binary_versions_update = ""
        for binary, version in binary_versions.items():
            binary_versions_update += f"* `{binary}`: v{version}\n"
        update = f"""The new release candidate will be produced with the following binaries:

{binary_versions_update}

We will begin setting up and coordinating the five standard staging tests when the RC is ready.
        """

        update_url = create_project_update(project_id, update, Team.Releases)
        print(f"Project update: {update_url}")
    except Exception as e:
        print(f"Error creating release: {e}")
        sys.exit(1)

def breaking(path: str):
    """Check if any PRs in the list have breaking changes.
    
    Args:
        path: Path to a file containing PR numbers, one per line
    """
    try:
        pr_numbers = read_pr_numbers(path)
        if not pr_numbers:
            print(f"Error: No PR numbers found in file {path}")
            sys.exit(1)
        
        breaking_prs = get_breaking_prs(pr_numbers)
        if breaking_prs:
            print("\n" + "="*16)
            print("BREAKING CHANGES")
            print("="*16)
            for pr in breaking_prs:
                print(f"#{pr['number']}: {pr['title']}")
                print(f"  Author: @{pr['author']}")
                print(f"  URL: {pr['url']}")
                print()
        else:
            print("\n✅ NO BREAKING CHANGES FOUND")
    except Exception as e:
        print(f"Error checking for breaking changes: {e}")
        sys.exit(1)

def breaking(path: str):
    """Check if any PRs in the list have breaking changes.
    
    Args:
        path: Path to a file containing PR numbers, one per line
    """
    try:
        pr_numbers = read_pr_numbers(path)
        if not pr_numbers:
            print(f"Error: No PR numbers found in file {path}")
            sys.exit(1)
        
        breaking_prs = get_breaking_prs(pr_numbers)
        if breaking_prs:
            print("\n" + "="*16)
            print("BREAKING CHANGES")
            print("="*16)
            for pr in breaking_prs:
                print(f"#{pr['number']}: {pr['title']}")
                print(f"  Author: @{pr['author']}")
                print(f"  URL: {pr['url']}")
                print()
        else:
            print("\n✅ NO BREAKING CHANGES FOUND")
    except Exception as e:
        print(f"Error checking for breaking changes: {e}")
        sys.exit(1)