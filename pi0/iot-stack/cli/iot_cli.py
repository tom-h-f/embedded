#!/usr/bin/env python3
"""IoT Stack Management CLI - Simple deployment and management tool for the homelab stack"""

import click
import subprocess
import sys
from pathlib import Path

# Configuration
REMOTE_HOST = "pi0"
REMOTE_PATH = "/opt/iot-stack"
LOCAL_PATH = Path(__file__).parent.parent.resolve()

# Colors
class Colors:
    BLUE = '\033[0;34m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    RED = '\033[0;31m'
    NC = '\033[0m'

def log_info(msg):
    click.echo(f"{Colors.BLUE}ℹ{Colors.NC} {msg}")

def log_success(msg):
    click.echo(f"{Colors.GREEN}✓{Colors.NC} {msg}")

def log_warn(msg):
    click.echo(f"{Colors.YELLOW}⚠{Colors.NC} {msg}")

def log_error(msg):
    click.echo(f"{Colors.RED}✗{Colors.NC} {msg}", err=True)

def run_command(cmd, check=True, capture=False):
    """Run a shell command"""
    try:
        if capture:
            result = subprocess.run(cmd, shell=True, check=check, capture_output=True, text=True)
            return result.returncode == 0, result.stdout, result.stderr
        else:
            result = subprocess.run(cmd, shell=True, check=check)
            return result.returncode == 0
    except subprocess.CalledProcessError as e:
        return False

def git_commit(message):
    """Commit changes to git"""
    log_info("Committing changes...")

    run_command(f"cd {LOCAL_PATH} && git add -A")

    # Check if there are changes to commit
    success = run_command(f"cd {LOCAL_PATH} && git diff --cached --quiet", check=False)
    if success:
        log_warn("No changes to commit")
        return False

    if run_command(f"cd {LOCAL_PATH} && git commit -m '{message}'"):
        log_success(f"Committed: {message}")
        return True
    return False

def git_push():
    """Push to remote"""
    log_info("Pushing to remote...")
    if run_command(f"cd {LOCAL_PATH} && git push"):
        log_success("Pushed to remote")
        return True
    return False

def sync_files():
    """Sync files to server"""
    log_info(f"Syncing files to {REMOTE_HOST}:{REMOTE_PATH}...")

    cmd = f"""rsync -avz --delete \
        --exclude '.git' \
        --exclude '.gitignore' \
        --exclude 'iot' \
        --exclude 'iot-cli' \
        --exclude '*.swp' \
        --exclude '.DS_Store' \
        '{LOCAL_PATH}/' '{REMOTE_HOST}:{REMOTE_PATH}/'"""

    if run_command(cmd):
        log_success("Files synced")
        return True
    return False

def restart_services(services):
    """Restart services on remote"""
    if not services:
        log_info(f"Restarting all services on {REMOTE_HOST}...")
        cmd = f"ssh {REMOTE_HOST} 'cd {REMOTE_PATH} && docker compose restart'"
        if run_command(cmd):
            log_success("All services restarted")
            return True
    else:
        services_str = " ".join(services)
        log_info(f"Restarting services: {services_str}")
        cmd = f"ssh {REMOTE_HOST} 'cd {REMOTE_PATH} && docker compose restart {services_str}'"
        if run_command(cmd):
            log_success(f"Services restarted: {services_str}")
            return True
    return False

def show_logs(service, follow):
    """Show logs for service(s)"""
    follow_flag = "-f" if follow else "--tail=50"

    if not service:
        log_info("Showing logs for all services...")
        cmd = f"ssh -t {REMOTE_HOST} 'cd {REMOTE_PATH} && docker compose logs {follow_flag}'"
    else:
        log_info(f"Showing logs for {service}...")
        cmd = f"ssh -t {REMOTE_HOST} 'cd {REMOTE_PATH} && docker compose logs {follow_flag} {service}'"

    run_command(cmd, check=False)

def show_status():
    """Show container status"""
    log_info(f"Container status on {REMOTE_HOST}:")
    cmd = f"ssh {REMOTE_HOST} 'cd {REMOTE_PATH} && docker compose ps'"
    run_command(cmd, check=False)

def exec_command(service, command):
    """Execute command in container"""
    log_info(f"Executing in {service}: {command}")
    cmd = f"ssh -t {REMOTE_HOST} 'cd {REMOTE_PATH} && docker compose exec {service} {command}'"
    run_command(cmd, check=False)

@click.group()
def cli():
    """IoT Stack Management CLI

    Simple deployment and management tool for the homelab stack.
    """
    pass

@cli.command()
@click.option('-c', '--commit', 'commit_msg', default=None, metavar='MESSAGE',
              help='Commit before syncing')
@click.option('-p', '--push', is_flag=True, help='Push after committing')
def sync(commit_msg, push):
    """Sync files to pi0 (rsync)"""
    if commit_msg is not None:
        msg = commit_msg if commit_msg else "Update iot-stack configuration"
        git_commit(msg)
        if push:
            git_push()

    sync_files()

@cli.command()
@click.argument('services', nargs=-1)
def restart(services):
    """Restart service(s) on pi0

    Examples:
        iot restart                        # Restart all services
        iot restart prometheus grafana     # Restart specific services
    """
    restart_services(services)

@cli.command()
@click.option('-c', '--commit', 'commit_msg', default=None, metavar='MESSAGE',
              help='Commit before deploying')
@click.option('-p', '--push', is_flag=True, help='Push after committing')
def deploy(commit_msg, push):
    """Sync + restart all services

    Examples:
        iot deploy                          # Sync and restart
        iot deploy -c "Update configs"      # Commit, sync, and restart
        iot deploy -c "Update" -p           # Commit, push, sync, and restart
    """
    if commit_msg is not None:
        msg = commit_msg if commit_msg else "Update iot-stack configuration"
        git_commit(msg)
        if push:
            git_push()

    if sync_files():
        restart_services([])

@cli.command()
@click.argument('service', required=False)
@click.option('-f', '--follow', is_flag=True, help='Follow logs')
def logs(service, follow):
    """Show logs for service (default: all)

    Examples:
        iot logs                    # Show all logs
        iot logs grafana            # Show Grafana logs
        iot logs grafana -f         # Follow Grafana logs
    """
    show_logs(service, follow)

@cli.command()
def status():
    """Show status of all containers"""
    show_status()

@cli.command()
@click.argument('message')
def commit(message):
    """Commit changes to git

    Example:
        iot commit "Add new dashboard"
    """
    if not message:
        log_error("Commit message required")
        sys.exit(1)
    git_commit(message)

@cli.command()
@click.argument('message', required=False)
def push(message):
    """Commit and push changes

    Example:
        iot push                            # Commit with default message
        iot push "Add new feature"          # Commit with custom message
    """
    msg = message if message else "Update iot-stack configuration"
    git_commit(msg)
    git_push()

@cli.command()
@click.argument('service')
@click.argument('command', nargs=-1, required=True)
def exec(service, command):
    """Execute command in container

    Example:
        iot exec grafana sh
    """
    if not service or not command:
        log_error("Usage: iot exec <service> <command>")
        sys.exit(1)
    exec_command(service, " ".join(command))

if __name__ == '__main__':
    cli()
