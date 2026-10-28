import json
import os
from pathlib import Path
from threading import RLock
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Simulated E-commerce Application")
FILE = Path(os.getenv("STATE_FILE", "/tmp/devops-state.json"))
LOCK = RLock()
BASE = {
    "scenario": "healthy", "version": "v1.0", "health": "ok", "http_status": 200,
    "cpu": 18, "memory_percent": 42, "disk_percent": 38, "latency_ms": 85,
    "traffic_rps": 120, "queue_depth": 4, "dependency_status": "ok",
    "auth_failures": 0, "certificate_days_remaining": 90, "container_restarts": 0,
    "rate_limit_count": 0, "error_count": 0, "alert_override": [],
    "logs": ["INFO checkout service healthy"],
    "deployments": ["v1.0 stable deployment"], "config_changes": [],
    "processes": ["python app.py 8% CPU, 42% memory"]
}
SCENARIOS = {
    "healthy": {**BASE},
    "bad_deployment": {**BASE, "scenario": "bad_deployment", "version": "v2.0", "health": "degraded", "http_status": 503, "cpu": 65, "error_count": 22, "logs": ["ERROR checkout HTTP 503 after deploy", "ERROR database connection pool exhausted"], "deployments": ["v2.0 deployed 5 minutes ago", "v1.0 stable deployment"]},
    "cpu_spike": {**BASE, "scenario": "cpu_spike", "health": "degraded", "cpu": 96, "error_count": 3, "logs": ["ERROR request timeout", "WARN CPU saturation"], "processes": ["python worker 92% CPU"]},
    "database_failure": {**BASE, "scenario": "database_failure", "health": "degraded", "http_status": 503, "dependency_status": "database_unreachable", "error_count": 35, "logs": ["ERROR database connection refused", "ERROR checkout HTTP 503"]},
    "memory_pressure": {**BASE, "scenario": "memory_pressure", "health": "degraded", "http_status": 503, "memory_percent": 98, "error_count": 9, "logs": ["ERROR out of memory", "WARN worker killed"], "processes": ["python worker memory 98%"]},
    "network_latency": {**BASE, "scenario": "network_latency", "health": "degraded", "http_status": 504, "latency_ms": 4200, "error_count": 16, "logs": ["WARN upstream latency above 4 seconds", "ERROR checkout upstream request timed out"]},
    "disk_pressure": {**BASE, "scenario": "disk_pressure", "health": "degraded", "http_status": 503, "disk_percent": 98, "error_count": 7, "logs": ["WARN disk usage 98%", "ERROR unable to write temporary checkout file"]},
    "dependency_timeout": {**BASE, "scenario": "dependency_timeout", "health": "degraded", "http_status": 504, "dependency_status": "payment_gateway_timeout", "latency_ms": 3500, "error_count": 18, "logs": ["ERROR payment gateway timeout", "ERROR checkout dependency call exceeded deadline"]},
    "config_drift": {**BASE, "scenario": "config_drift", "health": "degraded", "http_status": 503, "error_count": 11, "config_changes": ["checkout timeout changed from 3s to 30ms", "pool size changed from 20 to 2"], "logs": ["ERROR checkout requests failing after config change", "WARN configuration differs from approved baseline"]},
    "traffic_spike": {**BASE, "scenario": "traffic_spike", "health": "degraded", "http_status": 503, "cpu": 89, "traffic_rps": 1850, "queue_depth": 740, "error_count": 24, "logs": ["WARN request rate 1850 requests/sec", "ERROR checkout queue backlog exceeded threshold"]},
    "auth_failure": {**BASE, "scenario": "auth_failure", "health": "degraded", "http_status": 401, "auth_failures": 240, "error_count": 12, "logs": ["WARN elevated authentication failures", "ERROR checkout token validation failures"]},
    "container_crashloop": {**BASE, "scenario": "container_crashloop", "health": "degraded", "http_status": 503, "container_restarts": 14, "error_count": 20, "logs": ["ERROR checkout container restarted repeatedly", "WARN readiness probe failed"], "processes": ["checkout process restarting; uptime 4 seconds"]},
    "queue_backlog": {**BASE, "scenario": "queue_backlog", "health": "degraded", "http_status": 503, "queue_depth": 980, "error_count": 13, "logs": ["WARN queue depth 980", "ERROR checkout jobs delayed beyond SLA"]},
    "certificate_expiry": {**BASE, "scenario": "certificate_expiry", "health": "degraded", "http_status": 495, "certificate_days_remaining": 1, "error_count": 5, "logs": ["WARN TLS certificate expires in 1 day", "ERROR TLS handshake failed for some clients"]},
    "rate_limit": {**BASE, "scenario": "rate_limit", "health": "degraded", "http_status": 429, "rate_limit_count": 320, "error_count": 8, "logs": ["WARN rate limit responses increased", "INFO checkout throttled burst traffic"]},
    "stale_alert": {**BASE, "scenario": "stale_alert", "alert_override": ["STALE ALERT: old CPU alert; current metrics recovered"], "logs": ["INFO checkout service healthy", "INFO previous CPU alert has recovered"]},
    "intermittent_errors": {**BASE, "scenario": "intermittent_errors", "health": "degraded", "http_status": 502, "error_count": 6, "latency_ms": 1700, "logs": ["WARN intermittent upstream failures", "ERROR 6 checkout requests returned HTTP 502"]},
}
SCENARIO_DESCRIPTIONS = {
    "healthy": "Baseline: service healthy, low CPU, no errors.",
    "bad_deployment": "A new version correlates with checkout failures.",
    "cpu_spike": "CPU saturation and a high-CPU worker.",
    "database_failure": "Database connection failures and checkout 503s.",
    "memory_pressure": "Memory exhaustion and worker termination.",
    "network_latency": "High upstream latency and gateway timeouts.",
    "disk_pressure": "Disk nearly full, causing write failures.",
    "dependency_timeout": "Payment gateway calls are timing out.",
    "config_drift": "Runtime configuration differs from the approved baseline.",
    "traffic_spike": "Traffic surge with elevated queue depth and errors.",
    "auth_failure": "Unusual authentication failures and token errors.",
    "container_crashloop": "Repeated container restarts and failed readiness probes.",
    "queue_backlog": "Background work queue is growing beyond the service target.",
    "certificate_expiry": "TLS certificate expires soon and handshake errors appear.",
    "rate_limit": "Many requests are being throttled with HTTP 429.",
    "stale_alert": "A stale alert remains, but current metrics are healthy.",
    "intermittent_errors": "Occasional 502 errors and elevated latency.",
}

def read_state():
    with LOCK:
        if not FILE.exists():
            FILE.parent.mkdir(parents=True, exist_ok=True)
            FILE.write_text(json.dumps(BASE))
        return json.loads(FILE.read_text())

def write_state(state):
    with LOCK:
        FILE.parent.mkdir(parents=True, exist_ok=True)
        temp = FILE.with_suffix(".tmp")
        temp.write_text(json.dumps(state))
        temp.replace(FILE)
        return state

class Scenario(BaseModel):
    scenario: str

@app.get("/")
def home():
    s = read_state()
    return {"service": "checkout", "version": s["version"], "status": s["http_status"]}

@app.get("/health")
def health():
    s = read_state()
    return {"status": s["health"], "http_status": s["http_status"], "version": s["version"]}

@app.get("/state")
def state():
    return read_state()

@app.get("/scenarios")
def scenarios():
    return list(SCENARIOS)

@app.get("/scenario-details")
def scenario_details():
    return [{"id": key, "description": SCENARIO_DESCRIPTIONS[key]} for key in SCENARIOS]

@app.post("/simulate")
def simulate(body: Scenario):
    if body.scenario not in SCENARIOS:
        raise HTTPException(400, "Unknown scenario")
    return write_state(dict(SCENARIOS[body.scenario]))

@app.post("/reset")
def reset():
    return write_state(dict(BASE))

@app.post("/internal/restore")
def restore():
    # Demo-only endpoint, never deploy this application as a production control plane.
    return write_state(dict(BASE))
