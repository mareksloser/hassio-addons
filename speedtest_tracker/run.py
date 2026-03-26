#!/usr/bin/env python3
"""Speedtest Tracker addon - polls API and pushes sensors to HA via Supervisor API."""

import json
import logging
import os
import signal
import sys
import time
from pathlib import Path

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("speedtest_tracker")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

OPTIONS_PATH = Path("/data/options.json")
SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN")
HA_API_URL = "http://supervisor/core/api"


def load_config() -> dict:
    """Load addon configuration."""
    if not OPTIONS_PATH.exists():
        log.error("Options file not found at %s", OPTIONS_PATH)
        sys.exit(1)
    with open(OPTIONS_PATH) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# HA Supervisor API helpers
# ---------------------------------------------------------------------------

def ha_set_state(entity_id: str, state, attributes: dict) -> bool:
    """Set entity state via HA Supervisor API."""
    url = f"{HA_API_URL}/states/{entity_id}"
    headers = {
        "Authorization": f"Bearer {SUPERVISOR_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "state": state if state is not None else "unknown",
        "attributes": attributes,
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        resp.raise_for_status()
        return True
    except requests.RequestException as e:
        log.error("Failed to set state for %s: %s", entity_id, e)
        return False


# ---------------------------------------------------------------------------
# Sensor definitions
# ---------------------------------------------------------------------------

SENSORS = [
    {
        "key": "download_speed",
        "name": "Speedtest Download Speed",
        "unit": "Mbps",
        "device_class": "data_rate",
        "state_class": "measurement",
        "icon": "mdi:download",
        "extract": lambda d: _round(d.get("download_bits"), 1_000_000),
    },
    {
        "key": "upload_speed",
        "name": "Speedtest Upload Speed",
        "unit": "Mbps",
        "device_class": "data_rate",
        "state_class": "measurement",
        "icon": "mdi:upload",
        "extract": lambda d: _round(d.get("upload_bits"), 1_000_000),
    },
    {
        "key": "download_speed_human",
        "name": "Speedtest Download (Human)",
        "icon": "mdi:download",
        "extract": lambda d: d.get("download_bits_human"),
    },
    {
        "key": "upload_speed_human",
        "name": "Speedtest Upload (Human)",
        "icon": "mdi:upload",
        "extract": lambda d: d.get("upload_bits_human"),
    },
    {
        "key": "ping",
        "name": "Speedtest Ping",
        "unit": "ms",
        "state_class": "measurement",
        "icon": "mdi:lan-pending",
        "extract": lambda d: d.get("ping"),
    },
    {
        "key": "ping_jitter",
        "name": "Speedtest Ping Jitter",
        "unit": "ms",
        "state_class": "measurement",
        "icon": "mdi:sine-wave",
        "extract": lambda d: _deep(d, "data", "ping", "jitter"),
    },
    {
        "key": "ping_low",
        "name": "Speedtest Ping Low",
        "unit": "ms",
        "state_class": "measurement",
        "icon": "mdi:arrow-down",
        "extract": lambda d: _deep(d, "data", "ping", "low"),
    },
    {
        "key": "ping_high",
        "name": "Speedtest Ping High",
        "unit": "ms",
        "state_class": "measurement",
        "icon": "mdi:arrow-up",
        "extract": lambda d: _deep(d, "data", "ping", "high"),
    },
    {
        "key": "download_latency",
        "name": "Speedtest Download Latency",
        "unit": "ms",
        "state_class": "measurement",
        "icon": "mdi:timer-outline",
        "extract": lambda d: _deep(d, "data", "download", "latency", "iqm"),
    },
    {
        "key": "download_latency_jitter",
        "name": "Speedtest Download Latency Jitter",
        "unit": "ms",
        "state_class": "measurement",
        "icon": "mdi:sine-wave",
        "extract": lambda d: _deep(d, "data", "download", "latency", "jitter"),
    },
    {
        "key": "upload_latency",
        "name": "Speedtest Upload Latency",
        "unit": "ms",
        "state_class": "measurement",
        "icon": "mdi:timer-outline",
        "extract": lambda d: _deep(d, "data", "upload", "latency", "iqm"),
    },
    {
        "key": "upload_latency_jitter",
        "name": "Speedtest Upload Latency Jitter",
        "unit": "ms",
        "state_class": "measurement",
        "icon": "mdi:sine-wave",
        "extract": lambda d: _deep(d, "data", "upload", "latency", "jitter"),
    },
    {
        "key": "packet_loss",
        "name": "Speedtest Packet Loss",
        "unit": "%",
        "state_class": "measurement",
        "icon": "mdi:close-network-outline",
        "extract": lambda d: _deep(d, "data", "packetLoss"),
    },
    {
        "key": "isp",
        "name": "Speedtest ISP",
        "icon": "mdi:web",
        "extract": lambda d: _deep(d, "data", "isp"),
    },
    {
        "key": "server_name",
        "name": "Speedtest Server",
        "icon": "mdi:server-network",
        "extract": lambda d: _deep(d, "data", "server", "name"),
    },
    {
        "key": "server_location",
        "name": "Speedtest Server Location",
        "icon": "mdi:map-marker",
        "extract": lambda d: _deep(d, "data", "server", "location"),
    },
    {
        "key": "server_country",
        "name": "Speedtest Server Country",
        "icon": "mdi:flag",
        "extract": lambda d: _deep(d, "data", "server", "country"),
    },
    {
        "key": "server_host",
        "name": "Speedtest Server Host",
        "icon": "mdi:dns",
        "extract": lambda d: _deep(d, "data", "server", "host"),
    },
    {
        "key": "external_ip",
        "name": "Speedtest External IP",
        "icon": "mdi:ip-network",
        "extract": lambda d: _deep(d, "data", "interface", "externalIp"),
    },
    {
        "key": "internal_ip",
        "name": "Speedtest Internal IP",
        "icon": "mdi:ip-network-outline",
        "extract": lambda d: _deep(d, "data", "interface", "internalIp"),
    },
    {
        "key": "interface",
        "name": "Speedtest Interface",
        "icon": "mdi:ethernet",
        "extract": lambda d: _deep(d, "data", "interface", "name"),
    },
    {
        "key": "status",
        "name": "Speedtest Status",
        "icon": "mdi:check-circle-outline",
        "extract": lambda d: d.get("status"),
    },
    {
        "key": "result_url",
        "name": "Speedtest Result URL",
        "icon": "mdi:link-variant",
        "extract": lambda d: _deep(d, "data", "result", "url"),
    },
    {
        "key": "result_id",
        "name": "Speedtest Result ID",
        "icon": "mdi:identifier",
        "extract": lambda d: d.get("id"),
    },
    {
        "key": "last_test",
        "name": "Speedtest Last Test",
        "device_class": "timestamp",
        "icon": "mdi:clock-outline",
        "extract": lambda d: d.get("created_at"),
    },
]

BINARY_SENSORS = [
    {
        "key": "healthy",
        "name": "Speedtest Healthy",
        "device_class": "connectivity",
        "icon": "mdi:heart-pulse",
        "extract": lambda d: d.get("healthy"),
    },
    {
        "key": "vpn",
        "name": "Speedtest VPN Active",
        "icon": "mdi:vpn",
        "extract": lambda d: _deep(d, "data", "interface", "isVpn"),
    },
    {
        "key": "scheduled",
        "name": "Speedtest Scheduled",
        "icon": "mdi:calendar-clock",
        "extract": lambda d: d.get("scheduled"),
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _deep(data: dict, *keys):
    """Safely traverse nested dict."""
    current = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
        if current is None:
            return None
    return current


def _round(val, divisor: int) -> float | None:
    """Divide and round a value."""
    if val is None:
        return None
    return round(val / divisor, 2)


# ---------------------------------------------------------------------------
# Speedtest Tracker API
# ---------------------------------------------------------------------------

def fetch_latest(url: str, token: str) -> dict | None:
    """Fetch latest result from Speedtest Tracker API."""
    api_url = f"{url.rstrip('/')}/api/v1/results/latest"
    log.info("Fetching: %s", api_url)
    try:
        resp = requests.get(
            api_url,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
            },
            timeout=30,
        )
        log.info("Response status: %s", resp.status_code)
        resp.raise_for_status()
        body = resp.json()

        # API wraps result in {"data": {...}, "message": "ok"}
        data = body.get("data", body) if isinstance(body, dict) else body

        log.info("Got result ID: %s", data.get("id") if isinstance(data, dict) else None)
        return data
    except Exception as e:
        log.error("Failed to fetch speedtest result: %s: %s", type(e).__name__, e)
        return None


# ---------------------------------------------------------------------------
# Push sensors to HA
# ---------------------------------------------------------------------------

def push_sensors(data: dict) -> None:
    """Extract values and push all sensors to HA."""
    log.info("Pushing %d sensors to HA...", len(SENSORS) + len(BINARY_SENSORS))
    for sensor in SENSORS:
        entity_id = f"sensor.speedtest_tracker_{sensor['key']}"
        value = sensor["extract"](data)

        attributes = {
            "friendly_name": sensor["name"],
            "icon": sensor.get("icon"),
        }
        if sensor.get("unit"):
            attributes["unit_of_measurement"] = sensor["unit"]
        if sensor.get("device_class"):
            attributes["device_class"] = sensor["device_class"]
        if sensor.get("state_class"):
            attributes["state_class"] = sensor["state_class"]

        # Clean None values from attributes
        attributes = {k: v for k, v in attributes.items() if v is not None}

        ha_set_state(entity_id, value, attributes)

    for sensor in BINARY_SENSORS:
        entity_id = f"binary_sensor.speedtest_tracker_{sensor['key']}"
        raw = sensor["extract"](data)
        state = "on" if raw else "off"

        attributes = {
            "friendly_name": sensor["name"],
            "icon": sensor.get("icon"),
        }
        if sensor.get("device_class"):
            attributes["device_class"] = sensor["device_class"]

        attributes = {k: v for k, v in attributes.items() if v is not None}

        ha_set_state(entity_id, state, attributes)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

running = True


def handle_signal(signum, _frame):
    """Handle termination signal."""
    global running
    log.info("Received signal %s, shutting down...", signum)
    running = False


def main():
    """Main entry point."""
    global running

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    if not SUPERVISOR_TOKEN:
        log.error("SUPERVISOR_TOKEN not available. Is homeassistant_api enabled in config?")
        sys.exit(1)

    cfg = load_config()

    url = cfg["speedtest_tracker_url"]
    token = cfg["api_token"]
    interval = cfg.get("scan_interval", 300)

    if not token:
        log.error("API token is required. Configure it in addon settings.")
        sys.exit(1)

    log.info("Starting Speedtest Tracker addon")
    log.info("  Source: %s", url)
    log.info("  Interval: %ds", interval)
    log.info("  Sensors: %d + %d binary", len(SENSORS), len(BINARY_SENSORS))

    last_result_id = None

    while running:
        log.info("--- Poll cycle start ---")
        data = fetch_latest(url, token)

        if data:
            current_id = data.get("id")
            push_sensors(data)

            if current_id != last_result_id:
                dl = _round(data.get("download_bits"), 1_000_000)
                ul = _round(data.get("upload_bits"), 1_000_000)
                log.info(
                    "New result #%s: ↓ %s Mbps  ↑ %s Mbps  ping %s ms",
                    current_id, dl, ul, data.get("ping"),
                )
                last_result_id = current_id
            else:
                log.debug("Result #%s unchanged.", current_id)
        else:
            log.warning("No data, retrying in %ds.", interval)

        for _ in range(interval):
            if not running:
                break
            time.sleep(1)

    log.info("Stopped.")


if __name__ == "__main__":
    main()