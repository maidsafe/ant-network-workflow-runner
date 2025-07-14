# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Development Setup
```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate

# Install in development mode
pip install -e .
```

### Running the Application
```bash
# Set required environment variable
export WORKFLOW_RUNNER_PAT=your_github_token_here

# View available commands
runner --help

# Common workflow operations
runner workflows launch-network --path inputs/example.yml
runner workflows destroy-network --path inputs/example.yml
runner workflows ls

# Deployment management
runner deployments ls --details
runner deployments smoke-test --id <deployment_id>
runner deployments post --id <deployment_id>

# Debug mode
runner --debug <command>
```

### Database Management
```bash
# The application uses SQLite and Alembic for database management
# Database migrations are in alembic/versions/
alembic upgrade head  # Apply latest migrations
```

## Architecture

### Core Structure
- **CLI Entry Point**: `runner/main.py` - Main CLI parser with extensive subcommands
- **Workflow Management**: `runner/workflows.py` - GitHub Actions workflow dispatch and monitoring
- **GitHub Integration**: `runner/github.py` - GitHub API interactions using PyGithub
- **Database Layer**: `runner/database.py` and `runner/db.py` - SQLAlchemy models and database operations
- **Reporting**: `runner/reporting.py` - Generate reports for deployments and comparisons
- **Linear Integration**: `runner/linear.py` - Linear issue tracking integration

### Command Structure
The CLI is organized into major command groups:
- `client-deployments` - Manage client deployment testing
- `comparisons` - Compare multiple deployments for performance analysis
- `deployments` - Manage network deployments and smoke testing
- `releases` - Handle release management with Linear integration
- `workflows` - Direct GitHub Actions workflow operations

### Configuration System
- Input files are YAML-based with extensive configuration options
- Example configurations in `example-inputs/` directory
- Automatic hex address conversion for EVM-related fields in `main.py:load_yaml_config()`

### Data Models
Key entities tracked in the SQLite database:
- Workflow runs with GitHub Actions integration
- Network deployments with smoke test results
- Client deployments for testing scenarios
- Deployment comparisons for performance analysis
- Release tracking with Linear project integration

### External Integrations
- **GitHub Actions**: Dispatches workflows in `sn-testnet-workflows` repository
- **Digital Ocean**: Manages droplets for network infrastructure
- **Linear**: Creates and manages release planning projects
- **Slack**: Posts deployment notifications and results
- **Monitoring Stack**: Integrates with Grafana and ELK for environment monitoring

### Testing Strategy
This tool orchestrates complex network testing scenarios:
- Launches testnet networks with configurable parameters
- Manages uploader/downloader clients for load testing
- Provides smoke testing workflows for deployment validation
- Tracks performance comparisons across different network configurations