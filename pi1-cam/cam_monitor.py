#!/usr/bin/env python3
import os
import time
import subprocess
import requests
import json
import threading
import signal
import sys

# --- CONFIGURATION ---
SERVICE_NAME = "mediamtx"
RECORDINGS_DIR = "/opt/recordings"
RETENTION_HOURS = 24
LOKI_URL = "http://<GRAFANA_LOKI_IP>:3100/loki/api/v1/push"
MAINTENANCE_INTERVAL = 900  # 15 minutes
HEALTH_CHECK_INTERVAL = 60  # 1 minute
HOSTNAME = subprocess.check_output(["hostname"]).decode().strip()

# Global flag for graceful shutdown
running = True


def signal_handler(sig, frame):
    """Handle SIGTERM/SIGINT for graceful shutdown."""
    global running
    print("Shutdown signal received. Exiting gracefully...")
    running = False
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


class LokiLogger:
    """Handles batched log pushing to Grafana Loki."""

    def __init__(self, url):
        self.url = url
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    def push(self, message, labels=None):
        """Push a single log line to Loki with structured labels."""
        if labels is None:
            labels = {}

        # Default labels
        default_labels = {
            "job": "pi_camera_monitor",
            "host": HOSTNAME,
            "service": SERVICE_NAME,
        }
        default_labels.update(labels)

        # Convert labels dict to Loki format: {key="value", ...}
        label_str = ",".join([f'{k}="{v}"' for k, v in default_labels.items()])

        payload = {
            "streams": [
                {
                    "stream": label_str,
                    "values": [[str(int(time.time() * 1e9)), message]],
                }
            ]
        }

        try:
            resp = self.session.post(self.url, json=payload, timeout=3)
            if resp.status_code != 204:
                print(f"Loki push failed: {resp.status_code} - {resp.text}")
        except requests.exceptions.RequestException as e:
            print(f"Loki connection error: {e}")


def get_service_status():
    """Queries systemd for service health status."""
    try:
        result = subprocess.run(
            ["systemctl", "is-active", SERVICE_NAME],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip()  # "active", "inactive", "failed", etc.
    except subprocess.TimeoutExpired:
        return "timeout"
    except Exception as e:
        return f"error: {e}"


def restart_service(loki):
    """Restarts the systemd service."""
    loki.push(
        f"Service {SERVICE_NAME} is down. Attempting restart.",
        {"level": "error", "action": "restart"},
    )
    try:
        subprocess.run(
            ["sudo", "systemctl", "restart", SERVICE_NAME], check=True, timeout=10
        )
        loki.push(
            f"Service {SERVICE_NAME} restarted successfully.",
            {"level": "info", "action": "restart"},
        )
    except Exception as e:
        loki.push(
            f"Failed to restart {SERVICE_NAME}: {str(e)}",
            {"level": "critical", "action": "restart"},
        )


def stream_journal_logs(loki):
    """Continuously streams journalctl logs to Loki."""
    print(f"Starting journal log stream for {SERVICE_NAME}...")

    # Follow journal logs in JSON format for structured parsing
    process = subprocess.Popen(
        ["journalctl", "-u", SERVICE_NAME, "-f", "-o", "json", "-n", "0"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    while running:
        try:
            line = process.stdout.readline()
            if not line:
                time.sleep(0.1)
                continue

            # Parse systemd JSON log entry
            log_entry = json.loads(line)
            message = log_entry.get("MESSAGE", "")
            priority = log_entry.get("PRIORITY", "6")

            # Map syslog priority to log level
            level_map = {
                "0": "emergency",
                "1": "alert",
                "2": "critical",
                "3": "error",
                "4": "warning",
                "5": "notice",
                "6": "info",
                "7": "debug",
            }
            level = level_map.get(priority, "info")

            # Push to Loki with proper labels
            loki.push(
                message, {"level": level, "source": "journald", "unit": SERVICE_NAME}
            )

        except json.JSONDecodeError:
            continue
        except Exception as e:
            print(f"Log stream error: {e}")
            time.sleep(1)

    process.terminate()


def maintain_storage(loki):
    """Deletes recordings older than retention period."""
    if not os.path.exists(RECORDINGS_DIR):
        return

    now = time.time()
    cutoff = now - (RETENTION_HOURS * 3600)
    deleted_count = 0
    freed_bytes = 0

    try:
        for filename in os.listdir(RECORDINGS_DIR):
            filepath = os.path.join(RECORDINGS_DIR, filename)

            if not os.path.isfile(filepath):
                continue

            if filename.startswith("record_") and filename.endswith(".mp4"):
                mtime = os.path.getmtime(filepath)
                if mtime < cutoff:
                    size = os.path.getsize(filepath)
                    os.remove(filepath)
                    deleted_count += 1
                    freed_bytes += size

        if deleted_count > 0:
            freed_mb = freed_bytes / (1024 * 1024)
            msg = f"Storage maintenance: removed {deleted_count} segments, freed {freed_mb:.2f} MB"
            loki.push(msg, {"level": "info", "action": "cleanup"})
            print(msg)

    except Exception as e:
        loki.push(
            f"Storage maintenance failed: {str(e)}",
            {"level": "error", "action": "cleanup"},
        )


def health_check_loop(loki):
    """Periodically checks service health and triggers restarts if needed."""
    print(f"Starting health check loop (interval: {HEALTH_CHECK_INTERVAL}s)...")

    while running:
        status = get_service_status()

        if status not in ["active", "activating"]:
            restart_service(loki)

        time.sleep(HEALTH_CHECK_INTERVAL)


def maintenance_loop(loki):
    """Periodically performs storage cleanup."""
    print(f"Starting maintenance loop (interval: {MAINTENANCE_INTERVAL}s)...")

    while running:
        maintain_storage(loki)
        time.sleep(MAINTENANCE_INTERVAL)


def main():
    """Main orchestration."""
    loki = LokiLogger(LOKI_URL)

    # Startup log
    loki.push("Pi Camera Monitor started.", {"level": "info", "action": "startup"})
    print(f"Monitor started for service: {SERVICE_NAME}")

    # Create daemon threads
    threads = [
        threading.Thread(target=stream_journal_logs, args=(loki,), daemon=True),
        threading.Thread(target=health_check_loop, args=(loki,), daemon=True),
        threading.Thread(target=maintenance_loop, args=(loki,), daemon=True),
    ]

    for t in threads:
        t.start()

    # Keep main thread alive
    try:
        while running:
            time.sleep(1)
    except KeyboardInterrupt:
        pass

    loki.push("Pi Camera Monitor stopped.", {"level": "info", "action": "shutdown"})


if __name__ == "__main__":
    main()
