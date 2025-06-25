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
    ProjectLabel,
    IssueLabel,
    create_issue,
    create_project,
    create_project_update,
    get_projects,
    get_issue_label_id,
    get_state_id,
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

def new_rc(path: str, package_version: str, autonomi_repo_path: Optional[str] = None):
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
        prs_by_author = get_merged_prs_by_author(pr_numbers)
        
        projects = get_projects(Team.RELEASES)
        
        existing_project = next((p for p in projects if p["name"] == package_version), None)
        if existing_project:
            raise ValueError(f"Project for version {package_version} already exists")

        checklist = f"""## Staging Tests

- [ ] Environment comparison to evaluate standard metrics for improvements and regressions
- [ ] Upscale environment from 425 to 1975 generic nodes to ensure no regressions on open connections
- [ ] Upscale environment from 1 to 50 private nodes to ensure upload/download reliability
- [ ] Backwards compatibility: bootstrap {package_version} to network with previous version and observe metrics to ensure communication
- [ ] Backwards compatibility: upgrade various older node versions to {package_version}
- [ ] Mainnet client comparison to evaluate uploads/downloads for improvements and regressions
- [ ] Fresh installation of `node-launchpad` on Linux
- [ ] Fresh installation of `node-launchpad` on Windows
- [ ] Fresh installation of `node-launchpad` on macOS
- [ ] Upgrade `node-launchpad` on Linux
- [ ] Upgrade `node-launchpad` on Windows
- [ ] Upgrade `node-launchpad` on macOS"""

        content = f"{checklist}\n\n{binary_versions_markdown}\n\n## Merged Pull Requests\n\n{prs_by_author}"
        project_id = create_project(
            f"Release Candidate {package_version}", "Full feature release from `main`", content, Team.RELEASES)
        
        qa_label_id = get_issue_label_id(IssueLabel.QA, Team.QA)
        in_progress_state_id = get_state_id("In Progress", Team.RELEASES)
        todo_state_id = get_state_id("Todo", Team.RELEASES)

        create_issue(
            f"Produce the release candidate", 
            None, 
            Team.RELEASES,
            project_id, 
            [qa_label_id], 
            in_progress_state_id, 
        )
        create_issue(
            f"Setup the environment comparison test", 
            None, 
            Team.RELEASES,
            project_id, 
            [qa_label_id], 
            in_progress_state_id, 
        )
        create_issue(
            f"Setup the generic node upscaling test", 
            None, 
            Team.RELEASES,
            project_id, 
            [qa_label_id], 
            in_progress_state_id, 
        )
        create_issue(
            f"Setup the private node upscaling test", 
            None, 
            Team.RELEASES,
            project_id, 
            [qa_label_id], 
            in_progress_state_id, 
        )
        create_issue(
            f"Setup the basic backwards compatibility test", 
            None, 
            Team.RELEASES,
            project_id, 
            [qa_label_id], 
            in_progress_state_id, 
        )
        create_issue(
            f"Setup the comprehensive backwards compatibility test", 
            None, 
            Team.RELEASES,
            project_id, 
            [qa_label_id], 
            in_progress_state_id, 
        )
        create_issue(
            f"Setup the mainnet client comparison test", 
            None, 
            Team.RELEASES,
            project_id, 
            [qa_label_id], 
            in_progress_state_id, 
        )
        create_issue(
            f"Fresh installation of `node-launchpad` on Linux", 
            "Install the new version of `node-launchpad` and use it to launch the new node", 
            Team.RELEASES,
            project_id, 
            [qa_label_id], 
            todo_state_id, 
        )
        create_issue(
            f"Fresh installation of `node-launchpad` on Windows", 
            "Install the new version of `node-launchpad` and use it to launch the new node", 
            Team.RELEASES,
            project_id, 
            [qa_label_id], 
            todo_state_id, 
        )
        create_issue(
            f"Fresh installation of `node-launchpad` on macOS", 
            "Install the new version of `node-launchpad` and use it to launch the new node", 
            Team.RELEASES,
            project_id, 
            [qa_label_id], 
            todo_state_id, 
        )
        create_issue(
            f"Upgrade `node-launchpad` on Linux", 
            "Upgrade `node-launchpad` then use it to upgrade nodes on a previous version", 
            Team.RELEASES,
            project_id, 
            [qa_label_id], 
            todo_state_id, 
        )
        create_issue(
            f"Upgrade `node-launchpad` on Windows", 
            "Upgrade `node-launchpad` then use it to upgrade nodes on a previous version", 
            Team.RELEASES,
            project_id, 
            [qa_label_id], 
            todo_state_id, 
        )
        create_issue(
            f"Upgrade `node-launchpad` on macOS", 
            "Upgrade `node-launchpad` then use it to upgrade nodes on a previous version", 
            Team.RELEASES,
            project_id, 
            [qa_label_id], 
            todo_state_id, 
        )

        binary_versions_update = ""
        for binary, version in binary_versions.items():
            binary_versions_update += f"* `{binary}`: v{version}\n"
        update = f"""The new release candidate will be produced with the following binaries:

{binary_versions_update}

We will begin setting up and coordinating the five standard staging tests when the RC is ready.
        """

        update_url = create_project_update(project_id, update, Team.RELEASES)
        print(f"Project update: {update_url}")
    except Exception as e:
        print(f"Error creating release: {e}")
        sys.exit(1)

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
        prs_by_author = get_merged_prs_by_author(pr_numbers)
        
        projects = get_projects(Team.RELEASES)
        
        existing_project = next((p for p in projects if p["name"] == package_version), None)
        if existing_project:
            raise ValueError(f"Project for version {package_version} already exists")

        content = f"{binary_versions_markdown}\n\n## Merged Pull Requests\n\n{prs_by_author}"
        project_id = create_project(
            f"Release {package_version}", "Full feature release from `main`", content, Team.RELEASES)
        
        qa_label_id = get_issue_label_id(IssueLabel.QA, Team.QA)
        in_progress_state_id = get_state_id("In Progress", Team.RELEASES)
        todo_state_id = get_state_id("Todo", Team.RELEASES)

        create_issue(
            f"Produce changelog", 
            None, 
            Team.RELEASES, 
            project_id, 
            [qa_label_id], 
            in_progress_state_id, 
        )
        create_issue(
            f"Prepare community announcement and other documentation", 
            "The announcement and any other documentation should include instructions specific to this release", 
            Team.RELEASES, 
            project_id, 
            [qa_label_id], 
            todo_state_id, 
        )
        create_issue(
            f"Update minimum version for emissions", 
            "If relevant for this release we should update the minimum eligible node version on the emissions service.",
            Team.RELEASES, 
            project_id, 
            [qa_label_id], 
            todo_state_id, 
        )
        create_issue(
            f"Produce the stable release", 
            """The process is as follows:

- [ ] On the RC branch: promote the RC version numbers to stable by removing the `-rc` suffix
- [ ] On the RC branch: finalise the changelog
- [ ] Create a PR to merge the RC branch into `main` (conflicts may need to be resolved)
- [ ] Create a PR to merge the RC branch into `stable`
- [ ] Run the `release` workflow on `stable` with a 4MB chunk size
- [ ] Update the description of the Github release""", 
            Team.RELEASES, 
            project_id, 
            [qa_label_id], 
            todo_state_id, 
        )
        create_issue(
            f"Publish Rust crates", 
            """Right now this is done manually because the Github build agent doesn't have enough disk space.

It is done by running `release-plz release` at the root of the repository.""",
            Team.RELEASES, 
            project_id, 
            [qa_label_id], 
            todo_state_id, 
        )
        create_issue(
            f"Publish Python bindings", 
            "Right now this is done by David because he has the setup for publishing to PyPI.",
            Team.RELEASES, 
            project_id, 
            [qa_label_id], 
            todo_state_id, 
        )
        create_issue(
            f"Publish NodeJS bindings", 
            "This can be done by running a workflow after the release.",
            Team.RELEASES, 
            project_id, 
            [qa_label_id], 
            todo_state_id, 
        )
        create_issue(
            f"Upgrade nodes hosted by MaidSafe", 
            "All the nodes in our own production environment should be upgraded to this release.",
            Team.RELEASES, 
            project_id, 
            [qa_label_id], 
            todo_state_id, 
        )

        binary_versions_update = ""
        for binary, version in binary_versions.items():
            binary_versions_update += f"* `{binary}`: v{version}\n"
        update = f"""{binary_versions_update}

We will begin setting up and coordinating the five standard staging tests when the RC is ready.
        """

        update_url = create_project_update(project_id, update, Team.RELEASES)
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
