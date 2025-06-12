#!/usr/bin/env python

import os
import toml
from collections import defaultdict
from github import Github
from pathlib import Path

def has_breaking_change(commits):
    for commit in commits:
        commit_message = commit.commit.message
        if '!' in commit_message.split('\n')[0] or 'BREAKING CHANGE' in commit_message:
            return True
    return False

def read_pr_numbers(file_path):
    with open(file_path, 'r') as file:
        return [int(line.strip()) for line in file]

def get_crate_version(crate_name):
    cargo_toml_path = Path(f"{crate_name}/Cargo.toml")
    if not cargo_toml_path.exists():
        raise FileNotFoundError(f"Cargo.toml not found for crate {crate_name}")
    
    with open(cargo_toml_path, 'r') as f:
        cargo_toml = toml.load(f)
    
    version = cargo_toml.get('package', {}).get('version')
    if not version:
        raise ValueError(f"Version not found in Cargo.toml for crate {crate_name}")
    return version

def get_pr_list(pr_numbers):
    token = os.getenv("ANT_RUNNER_PR_LIST_GITHUB_TOKEN")
    if not token:
        raise Exception("The ANT_RUNNER_PR_LIST_GITHUB_TOKEN environment variable must be set")

    g = Github(token)
    repo = g.get_repo("maidsafe/autonomi")

    pulls = []
    for pr_num in pr_numbers:
        print(f"Processing #{pr_num}...")
        pull = repo.get_pull(pr_num)
        if not pull.closed_at and not pull.merged_at:
            raise Exception(f"PR {pr_num} has not been closed yet")
        commits = pull.get_commits()
        breaking = has_breaking_change(commits)
        pulls.append({
            "number": pull.number,
            "title": pull.title,
            "author": pull.user.login,
            "closed_at": pull.closed_at,
            "breaking": breaking,
            "commits": commits
        })
    pulls.sort(key=lambda pr: pr["closed_at"])

    markdown_lines = []
    for pr in pulls:
        pr_number = pr["number"]
        closed_date = pr["closed_at"].date()
        breaking_text = "[BREAKING]" if pr["breaking"] else ""
        markdown_lines.append(f"{closed_date} [#{pr_number}](https://github.com/maidsafe/autonomi/pull/{pr_number}) -- {pr['title']} [@{pr['author']}] {breaking_text}")
    return markdown_lines

def get_release_description(pr_numbers):
    crate_binary_map = {
        "ant-node": "antnode",
        "ant-node-manager": "antctl",
        "ant-cli": "ant",
        "nat-detection": "nat-detection",
        "node-launchpad": "node-launchpad"
    }

    markdown_doc = []
    markdown_doc.append("## Binary Versions\n")
    for crate, binary in crate_binary_map.items():
        version = get_crate_version(crate)
        if crate == "ant-node-manager":
            markdown_doc.append(f"* `antctld`: v{version}")
        markdown_doc.append(f"* `{binary}`: v{version}")
    
    markdown_doc.append("\n## Merged Pull Requests\n")
    markdown_doc.extend(get_pr_list(pr_numbers))

    markdown_doc.append("\n## Detailed Changes\n")

    markdown_doc = "\n".join(markdown_doc)
    return markdown_doc

def get_merged_prs_by_author(pr_numbers):
    """Get merged PRs by author.
    
    Args:
        pr_numbers: List of PR numbers to retrieve
        
    Returns:
        Formatted string with PRs grouped by author
        
    Raises:
        Exception: If any PR in the list is not closed
    """
    token = os.getenv("ANT_RUNNER_PR_LIST_GITHUB_TOKEN")
    if not token:
        raise Exception("The ANT_RUNNER_PR_LIST_GITHUB_TOKEN environment variable must be set")

    g = Github(token)
    repo = g.get_repo("maidsafe/autonomi")

    pulls = []
    for pr_num in pr_numbers:
        print(f"Processing #{pr_num}...")
        pull = repo.get_pull(pr_num)
        if not pull.closed_at:
            raise Exception(f"PR {pr_num} has not been closed yet")
        if not pull.merged_at:
            raise Exception(f"PR {pr_num} was closed but not merged")
        
        commits = pull.get_commits()
        breaking = has_breaking_change(commits)
        pulls.append({
            "number": pull.number,
            "title": pull.title,
            "author": pull.user.login,
            "closed_at": pull.closed_at,
            "breaking": breaking,
            "commits": commits
        })
    
    pulls.sort(key=lambda pr: pr["closed_at"])

    grouped_pulls = defaultdict(list)
    for pr in pulls:
        grouped_pulls[pr["author"]].append(pr)

    markdown_doc = []
    for author, prs in grouped_pulls.items():
        markdown_doc.append(f"@{author}")
        for pr in prs:
            pr_number = pr["number"]
            closed_date = pr["closed_at"].date()
            breaking_text = "[BREAKING]" if pr["breaking"] else ""
            markdown_doc.append(f"  {closed_date} [#{pr_number}](https://github.com/maidsafe/autonomi/pull/{pr_number}) -- {pr['title']} {breaking_text}")
        markdown_doc.append("")

    return "\n".join(markdown_doc)

def get_breaking_prs(pr_numbers):
    """Get breaking PRs.
    
    Args:
        pr_numbers: List of PR numbers to retrieve
    """
    token = os.getenv("ANT_RUNNER_PR_LIST_GITHUB_TOKEN")
    if not token:
        raise Exception("The ANT_RUNNER_PR_LIST_GITHUB_TOKEN environment variable must be set")

    g = Github(token)
    repo = g.get_repo("maidsafe/autonomi")

    breaking_prs = []
    for pr_num in pr_numbers:
        print(f"Processing #{pr_num}...")
        try:
            pull = repo.get_pull(pr_num)
            commits = pull.get_commits()
            
            if has_breaking_change(commits):
                breaking_prs.append({
                    "number": pr_num,
                    "title": pull.title,
                    "author": pull.user.login,
                    "url": pull.html_url
                })

        except Exception as e:
            print(f"Error processing PR #{pr_num}: {e}")
            continue
    return breaking_prs