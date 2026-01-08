# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is an embedded systems workspace containing multiple independent projects for ESP32, Raspberry Pi Pico, and Raspberry Pi servers. Each project directory is self-contained.

## Project Structure

- **bvr**: ESP32C6 with ST7789 LCD display (ESP-IDF project)
- **mini-weather-1**: Raspberry Pi Pico with DHT11 temp/humidity sensor and soil moisture sensor (MicroPython)
- **pi0/iot-stack**: Homelab infrastructure stack running on Raspberry Pi server (Docker Compose)
- **pi1-cam**: Camera monitoring and YOLO object detection system running on Raspberry Pi (Python)
- **tf1**: Cloud server monitoring stack (Docker Compose)
- **esp/esp-idf/v5.5.2**: ESP-IDF framework installation
- **docs**: Reference manuals and hardware schematics

## ESP32 Development (bvr project)

### Environment Setup

Before working with any ESP32 project, source the ESP-IDF environment:

```sh
cd ./esp
. ./export.sh  # Must be sourced, not executed
```

This sets up IDF_PATH and other required environment variables.

### Common Commands

All commands should be run from the project directory (e.g., `bvr/`):

```sh
# Configure project settings
idf.py menuconfig

# Build the project
idf.py build

# Flash to device (replace PORT with actual port like /dev/cu.usbserial-*)
idf.py -p PORT flash

# Monitor serial output
idf.py -p PORT monitor

# Flash and monitor in one command
idf.py -p PORT flash monitor

# Clean build
idf.py fullclean
```

### Project Structure

ESP-IDF projects follow a standard structure:
- `CMakeLists.txt`: Top-level build configuration
- `main/`: Source code directory containing main.c and component CMakeLists.txt
- `sdkconfig`: Generated configuration file (do not edit manually, use menuconfig)
- `build/`: Build artifacts (generated)

The bvr project uses:
- FreeRTOS for task management
- ST7789 LCD driver (custom component in main/LCD_Driver/)
- Embedded binary files using CMake's EMBED_FILES feature

## Raspberry Pi Pico Development (mini-weather-1)

This project uses MicroPython. The code monitors environment sensors:
- DHT11 on GPIO 16 (temperature and humidity)
- Capacitive soil moisture sensor on ADC GPIO 27 with power control on GPIO 22

The soil sensor power pin is toggled to prevent electrode corrosion between readings.

## Homelab Stack (pi0/iot-stack)

Full observability and home automation stack deployed via Docker Compose on pi0:

```sh
cd pi0/iot-stack

# Start all services
docker compose up -d

# View logs
docker compose logs -f [service_name]

# Stop services
docker compose down

# Restart specific service
docker compose restart [service_name]
```

### Services

- **Homepage**: Service dashboard (port 3001)
- **Portainer**: Container management (port 9000)
- **Nginx Proxy Manager**: Reverse proxy (ports 80, 81, 443)
- **Pi-hole**: DNS and ad blocking (port 53, 8080)
- **Home Assistant**: Home automation (host network mode)
- **Prometheus**: Metrics collection (port 9090)
- **Grafana**: Visualization (port 3000)
- **Loki + Promtail**: Log aggregation (port 3100)
- **cAdvisor**: Container metrics
- **Node Exporter**: System metrics (port 9100)

All services have local DNS entries via Pi-hole (*.lan domains).

### Monitoring and Observability Architecture

The homelab uses a comprehensive monitoring stack that spans multiple machines over Tailscale VPN with intelligent DNS routing and service discovery.

#### Network Architecture

All machines are connected via **Tailscale VPN** under the tailnet: `meerkat-decibel.ts.net`

**Machine IPs**:
- **pi0** (main homelab server):
  - Tailscale: 100.70.68.91
  - Local network: 192.168.0.38
- **pi1** (camera server):
  - Tailscale: 100.99.168.84
- **tf1** (cloud server):
  - Tailscale: 100.93.107.4
- **Tailscale MagicDNS**: 100.100.100.100 (resolves *.ts.net domains)

#### DNS Architecture

The homelab uses a multi-tier DNS setup with Pi-hole as the primary resolver, integrated with Tailscale MagicDNS.

**Pi-hole Configuration** (`/opt/iot-stack/pihole/dnsmasq/05-monitoring-srv.conf`):
```
server=/ts.net/100.100.100.100    # Forward .ts.net queries to Tailscale MagicDNS

# SRV records for Prometheus service discovery
srv-host=_metrics._tcp.meerkat-decibel.ts.net,pi1.meerkat-decibel.ts.net,9100,0,10
srv-host=_metrics._tcp.meerkat-decibel.ts.net,tf1.meerkat-decibel.ts.net,9100,0,10

# Static A records for Tailscale hosts
host-record=pi0.meerkat-decibel.ts.net,100.70.68.91
host-record=pi1.meerkat-decibel.ts.net,100.99.168.84
host-record=tf1.meerkat-decibel.ts.net,100.93.107.4
```

**Pi-hole Upstream DNS** (`/opt/iot-stack/pihole/etc/pihole.toml`):
- Primary: 100.100.100.100 (Tailscale MagicDNS)
- Fallback: OpenDNS (208.67.222.222, 208.67.220.220)
- Fallback: Cloudflare (1.1.1.1, 1.0.0.1)
- Fallback: Mullvad DNS

**DNS Resolution Flow**:
1. Client queries Pi-hole (100.70.68.91 or 192.168.0.38)
2. For `*.ts.net` domains: Pi-hole serves static A records OR forwards to Tailscale MagicDNS
3. For SRV records: Pi-hole returns service discovery information (e.g., `_metrics._tcp`)
4. For local domains: Pi-hole resolves `.lan` via static entries
5. For other domains: Pi-hole blocks ads, then forwards to upstream DNS

#### Nginx Proxy Manager

Nginx Proxy Manager provides clean domain-based access to all services running on pi0.

**Configuration Location**: `/opt/iot-stack/nginx/data/nginx/proxy_host/*.conf`

**Proxy Redirects**:

| Domain | Target Server | Port | Protocol | Service |
|--------|---------------|------|----------|---------|
| home.lan | 100.70.68.91 | 3001 | HTTP | Homepage Dashboard |
| homeassistant.lan | 192.168.0.38 | 8123 | HTTP | Home Assistant |
| grafana.lan | 192.168.0.38 | 3000 | HTTP | Grafana Dashboard |
| prometheus.lan | 100.70.68.91 | 9090 | HTTP | Prometheus |
| pihole.lan | 192.168.0.38 | 8080 | HTTP | Pi-hole Web UI |
| loki.lan | 192.168.0.38 | 3100 | HTTP | Loki API |
| containers.lan | 192.168.0.38 | 9000 | HTTP | Portainer |
| npm.lan | 192.168.0.38 | 81 | HTTP | NPM Admin Panel |
| data.lan | 192.168.0.38 | 3000 | HTTP | Grafana (alias) |
| data.lan | 192.168.0.38 | 3000 | HTTPS | Grafana (HTTPS) |

**How It Works**:
- Nginx listens on ports 80 (HTTP), 443 (HTTPS), and 81 (admin panel)
- When you access `http://grafana.lan`, Nginx proxies to `192.168.0.38:3000`
- The `.lan` TLD is used for all local services
- Pi-hole DNS resolves these domains to the Nginx Proxy Manager IP

#### Monitoring Data Flow

```
Host Systems (pi0, pi1, tf1)
    ↓ (expose metrics on port 9100)
node-exporter ──────────────┐
                            │
Docker Containers (pi0)     │
    ↓ (expose metrics)      │
cAdvisor:8080 ──────────────┤
Promtail:9080 ──────────────┤
                            │
                            ↓ (scrape every 15s)
                       Prometheus:9090
                            │
                            ↓ (query)
                       Grafana:3000
                            ↑ (query logs)
Log Files ──→ Promtail ──→ Loki:3100
```

#### Prometheus Scrape Configuration

**File**: `/opt/iot-stack/prometheus/prometheus.yml`

**Scrape Jobs**:

1. **Static Scrape Jobs** (local services on pi0 via Docker network):
   - `prometheus`: localhost:9090 (self-monitoring)
   - `node-exporter`: node-exporter:9100 (pi0 system metrics)
   - `cadvisor`: cadvisor:8080 (Docker container metrics)

2. **Docker Service Discovery** (`docker-discovery` job):
   - Automatically discovers containers with label `prometheus_scrape=true`
   - Currently scrapes: promtail
   - Excludes: cadvisor, node-exporter (already scraped via static configs to avoid duplicates)

3. **DNS Service Discovery** (`tailscale-nodes` job):
   - Queries SRV record: `_metrics._tcp.meerkat-decibel.ts.net`
   - Discovers remote machines: pi1 node-exporter:9100, tf1 node-exporter:9100
   - Refresh interval: 30 seconds

**Prometheus DNS Configuration**:
```yaml
dns:
  - 100.70.68.91      # Pi-hole Tailscale IP (for SRV records and local resolution)
  - 100.100.100.100   # Tailscale MagicDNS (for .ts.net A records)
```

#### Metrics Exporters

**node-exporter** (runs on both pi0 and pi1):
- Exposes system metrics: CPU, memory, disk, network
- Port: 9100
- Metrics: `node_*` (e.g., `node_cpu_seconds_total`, `node_memory_MemAvailable_bytes`)

**cAdvisor** (runs on pi0):
- Exposes Docker container metrics: CPU, memory, network, disk I/O
- Port: 8080 (externally: 8081)
- Optimizations for lower CPU usage:
  - `--housekeeping_interval=15s` (default is 1s)
  - `--docker_only=true` (only monitor Docker containers)
- Requires privileged mode and `/sys/fs/cgroup:/cgroup:ro` mount
- Metrics: `container_*` (e.g., `container_cpu_usage_seconds_total`, `container_memory_usage_bytes`)

#### Log Collection

**Promtail**:
- Collects logs from:
  - `/var/log/*log` (system logs)
  - `/var/lib/docker/containers` (Docker container stdout/stderr)
- Ships to Loki at `http://loki:3100/loki/api/v1/push`
- Labels: `job=varlogs`
- Position tracking: `/tmp/positions.yaml`

**Loki**:
- Storage: Filesystem-based at `/loki/chunks` and `/loki/rules`
- Schema: v13 TSDB with 24h index period
- Listening on port 3100 (HTTP) and 9096 (gRPC)

#### Grafana Dashboard

**Location**: `/Users/tom/iot-dashboard.json`

**Dashboard Sections**:
1. **Active Alerts**: Shows firing alerts from Prometheus
2. **System Overview**: Host CPU, memory, disk usage, network traffic (from node-exporter)
3. **Container Metrics**: Per-container CPU, memory, network I/O, disk I/O (from cAdvisor)
4. **Logs**: All system/container logs and filtered error/warning logs (from Loki)
5. **Service Details**: Prometheus target health and TSDB statistics

**Key Features**:
- Distinguishes between machines using `{{instance}}` labels
- Network interfaces shown as `instance/device` (e.g., `pi1.meerkat-decibel.ts.net:9100/eth0`)
- Container names from cAdvisor `name` label
- No duplicate scraping (each target scraped exactly once)
- Time range: Default 6 hours

#### Service Discovery Workflow

When Prometheus starts, it discovers remote metrics exporters via DNS-SD:

1. Prometheus queries DNS for SRV record: `_metrics._tcp.meerkat-decibel.ts.net`
2. Pi-hole returns multiple SRV records:
   - `0 10 9100 pi1.meerkat-decibel.ts.net.`
   - `0 10 9100 tf1.meerkat-decibel.ts.net.`
3. Prometheus resolves hostnames via Pi-hole:
   - `pi1.meerkat-decibel.ts.net` to `100.99.168.84`
   - `tf1.meerkat-decibel.ts.net` to `100.93.107.4`
4. Prometheus begins scraping both endpoints every 15 seconds
5. Metrics appear in Grafana with labels:
   - `instance="pi1.meerkat-decibel.ts.net:9100"`
   - `instance="tf1.meerkat-decibel.ts.net:9100"`

#### Service Access URLs

**Via Nginx Proxy Manager** (clean domain names):
- **Homepage**: http://home.lan → 100.70.68.91:3001
- **Home Assistant**: http://homeassistant.lan → 192.168.0.38:8123
- **Grafana**: http://grafana.lan → 192.168.0.38:3000
- **Prometheus**: http://prometheus.lan → 100.70.68.91:9090
- **Pi-hole**: http://pihole.lan → 192.168.0.38:8080
- **Loki**: http://loki.lan → 192.168.0.38:3100
- **Portainer**: http://containers.lan → 192.168.0.38:9000
- **NPM Admin**: http://npm.lan:81 → 192.168.0.38:81

**Direct Access** (via IP:port):
- **Homepage**: http://192.168.0.38:3001
- **Home Assistant**: http://192.168.0.38:8123
- **Grafana**: http://192.168.0.38:3000
- **Prometheus**: http://192.168.0.38:9090
- **Pi-hole**: http://192.168.0.38:8080
- **Loki**: http://192.168.0.38:3100
- **Portainer**: http://192.168.0.38:9000
- **cAdvisor**: http://192.168.0.38:8081
- **node-exporter**: http://192.168.0.38:9100

**Via Tailscale** (from anywhere on the VPN):
- All services accessible via: `http://pi0.meerkat-decibel.ts.net:<port>`
- Example: `http://pi0.meerkat-decibel.ts.net:3000` for Grafana

#### Container Dependencies

The Docker Compose stack is configured with proper startup order:
- `prometheus` depends on `cadvisor` and `node-exporter` (waits for metrics exporters)
- `nginx-proxy-manager` depends on `pihole` (waits for DNS to be ready)

This ensures services start in the correct sequence and can resolve dependencies immediately.

## Camera System (pi1-cam)

YOLO11-based object detection on RTSP camera stream. Runs on pi1.

```sh
cd pi1-cam

# Run object detection (requires environment variables)
uv run object_detection.py

# Start as service
./start_object_detector.sh
```

Required environment variables:
- `LOKI_URL`: Loki endpoint for logging detections
- `STREAM_URL`: RTSP stream URL
- `MODEL_NAME`: YOLO model file (default: yolo11n.pt)
- `CONF_THRESHOLD`: Detection confidence threshold (default: 0.6)

The system sends detection events to Loki for visualization in Grafana.

## Cloud Server (tf1)

Monitoring stack for the Hetzner cloud server. Runs node-exporter to expose system metrics.

```sh
cd tf1

# Start node-exporter
docker compose up -d

# View logs
docker compose logs -f node-exporter

# Stop services
docker compose down
```

The node-exporter is automatically discovered by Prometheus via DNS-SD (SRV records) and scraped every 15 seconds. Metrics are visible in Grafana under the instance label `tf1.meerkat-decibel.ts.net:9100`.

## Architecture Notes

### ESP32 Memory Management

The bvr project uses heap_caps_malloc with MALLOC_CAP_DMA for LCD framebuffers to ensure DMA-compatible memory allocation. Always free buffers after drawing operations to prevent memory leaks.

### Homelab Service Discovery

The Pi-hole DNS server provides local name resolution. Services are accessible at:
- `<service>.lan` for all services (e.g., grafana.lan, prometheus.lan)
- External access is routed through Nginx Proxy Manager with SSL

### Object Detection Pipeline

The pi1-cam system:
1. Connects to RTSP stream from camera
2. Processes every 12th frame (vid_stride) for efficiency
3. Deduplicates detections per frame sequence
4. Batches Loki pushes with unique timestamps
5. Uses session IDs to prevent stream collision

## Development Machines

- `tac2`: Local MacBook (development machine)
- `pi0`: Raspberry Pi running homelab stack
- `pi1`: Raspberry Pi running camera monitoring
- `tf1`: Hetzner cloud server

## TODO

When you read this file's section; if there are any items listed, notify the user that we still need to complete them. Once they are completed remove them from the file.

No outstanding TODOs.
