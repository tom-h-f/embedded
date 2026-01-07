# IoT Stack Management CLI

Simple deployment and management tool for the homelab stack.

## Setup

This tool uses `uv` for dependency management with a virtual environment.

Dependencies are managed in `pyproject.toml` and the virtual environment is at `.venv/`.

## Usage

The `iot` command is symlinked to `/Users/tom/Code/Embedded/iot` for easy access.

### Commands

```bash
# Sync files to pi0 (rsync)
iot sync
iot sync -c "Update configs"        # Commit before syncing
iot sync -c "Update" -p             # Commit and push before syncing

# Deploy: sync + restart all services
iot deploy
iot deploy -c "Update configs"      # Commit, sync, and restart
iot deploy -c -p                    # Commit, push, sync, and restart

# Restart services
iot restart                         # Restart all services
iot restart prometheus grafana      # Restart specific services

# View logs
iot logs                            # Show all logs
iot logs grafana                    # Show Grafana logs
iot logs grafana -f                 # Follow Grafana logs

# Container status
iot status

# Git operations
iot commit "Add new dashboard"      # Commit changes
iot push                            # Commit and push with default message
iot push "Add new feature"          # Commit and push with custom message

# Execute command in container
iot exec grafana sh                 # Open shell in Grafana container
```

## Configuration

- `REMOTE_HOST`: `pi0`
- `REMOTE_PATH`: `/opt/iot-stack`
- `LOCAL_PATH`: Automatically detected as the parent directory of iot-cli

## Development

To add new dependencies:

```bash
cd /Users/tom/Code/Embedded/pi0/iot-stack/iot-cli
uv add <package-name>
```

To modify the CLI, edit `iot_cli.py`.
