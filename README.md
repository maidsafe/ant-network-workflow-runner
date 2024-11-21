# Network Workflow Runner

A CLI for running Github Actions workflows that launch and manage Autonomi networks.

## Prerequisites

- Python 3.6 or higher
- Github personal access token with permission to run workflows

## Setup

1. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate
```

2. Install the package in development mode:
```bash
pip install -e .
```

3. Set up your personal access token:
```bash
export WORKFLOW_RUNNER_PAT=your_github_token_here
```

## Available Commands

There are several commands for managing network workflows. All commands support the following global options:

- `--debug`: Enable debug logging
- `--branch`: Specify the branch for the workflow (default: main)
- `--force`: Skip confirmation prompts

### Network Management Workflows

- Launch a new network:
```bash
runner launch-network --path <workflow-inputs-file>
```

- Destroy an existing network:
```bash
runner destroy-network --path <workflow-inputs-file>
```

- Upscale an existing network:
```bash
runner upscale-network --path <workflow-inputs-file>
```

### Listing Runs

- List workflow runs:
```bash
runner ls [--details]
```

- List deployments:
```bash
runner deployment ls [--details]
```

Deployments are created when the `launch-network` command is used.

### Node Operation Workflows

- Stop nodes:
```bash
runner stop-nodes --path <workflow-inputs-file>
```

- Kill specific droplets:
```bash
runner kill-droplets --path <workflow-inputs-file>
```

- Upgrade network nodes:
```bash
runner upgrade-network --path <workflow-inputs-file>
```

- Upgrade node manager:
```bash
runner upgrade-node-man --path <workflow-inputs-file>
```

### Telegraf Management Workflows

- Start telegraf:
```bash
runner start-telegraf --path <workflow-inputs-file>
```

- Stop telegraf:
```bash
runner stop-telegraf --path <workflow-inputs-file>
```

### Other Operations

- Update peer multiaddr:
```bash
runner update-peer --path <workflow-inputs-file>
```

- Upgrade uploaders:
```bash
runner upgrade-uploaders --path <workflow-inputs-file>
```

## Input Files

Workflows are launched using a set of inputs. For each command, there is an example input file. For whatever command you want to use, take the example file corresponding to the command and adapt it for your use case. Remove whatever optional inputs you don't want to use.

Examples can be found in the `example-inputs` directory:

- `launch_network.yml`: Configuration for launching a new network
- `destroy_network.yml`: Configuration for destroying a network
- `upgrade_network.yml`: Configuration for upgrading network nodes
- `upgrade_node_man.yml`: Configuration for upgrading the node manager
- `upgrade_uploaders.yml`: Configuration for upgrading uploaders
- `upscale_network.yml`: Configuration for upscaling a network
- `start_telegraf.yml`: Configuration for starting telegraf
- `stop_telegraf.yml`: Configuration for stopping telegraf
- `stop_nodes.yml`: Configuration for stopping nodes

Each file contains detailed comments explaining the available options and their usage.

## Database

The tool maintains a local SQLite database at `~/.local/share/safe/workflow_runs.db` to track workflow runs and deployments.
