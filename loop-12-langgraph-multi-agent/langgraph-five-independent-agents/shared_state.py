import json, os, tempfile
from pathlib import Path

STATE_FILE = os.getenv("STATE_FILE", "/data/state.json")
BASE = dict(cpu_percent=18, memory_percent=42, disk_percent=38, error_count=0, http_status=200,
            latency_ms=85, container_restarts=0, dependency_status="ok", queue_depth=4,
            rate_limit_count=0, traffic_rps=120, auth_failures=0, certificate_days_remaining=90)

# scenario: title, incident_expected, metric overrides, alerts, logs, version, config changes, health, processes
_RAW = {
 "healthy": ("Healthy baseline", False, {}, [], ["INFO checkout request completed status=200"], "v1.0", [], "healthy", ["checkout process running; uptime 3 days"]),
 "stale_alert": ("Stale / false-positive alert", False, {}, ["Historical high CPU alert (resolved)"], ["INFO alert resolved; checkout healthy"], "v1.0", [], "healthy", ["checkout process running; uptime 2 days"]),
 "bad_deployment": ("Bad deployment", True, dict(error_count=37,http_status=503,latency_ms=850,container_restarts=2), ["Checkout 5xx rate increased after deployment"], ["ERROR checkout handler exception after release v1.1","ERROR HTTP 503 returned"], "v1.1", ["Deployment changed from v1.0 to v1.1"], "degraded", ["checkout process running; uptime 12 minutes"]),
 "cpu_spike": ("CPU spike", True, dict(cpu_percent=96,error_count=8,latency_ms=1200,queue_depth=21,traffic_rps=170), ["CPU utilization above 90%"], ["WARN checkout latency elevated"], "v1.0", [], "healthy", ["checkout-worker CPU utilization elevated"]),
 "memory_pressure": ("Memory pressure", True, dict(memory_percent=97,error_count=12,http_status=500,container_restarts=5), ["Container memory above 95%"], ["ERROR worker memory allocation failed","WARN container restarted"], "v1.0", [], "degraded", ["checkout-worker memory usage elevated"]),
 "disk_pressure": ("Disk pressure", True, dict(disk_percent=98,error_count=5,http_status=500), ["Disk usage above 95%"], ["ERROR no space left on device"], "v1.0", [], "degraded", ["checkout process running; disk writes failing"]),
 "container_crashloop": ("Container crash loop", True, dict(error_count=20,http_status=503,container_restarts=14), ["container_crashloop detected"], ["ERROR checkout container restarted repeatedly"], "v1.0", [], "degraded", ["checkout process restarting; uptime 4 seconds"]),
 "database_failure": ("Database failure", True, dict(error_count=31,http_status=503,latency_ms=1800,dependency_status="database_unavailable",queue_depth=19), ["Database connection failures"], ["ERROR database connection refused","ERROR checkout transaction aborted"], "v1.0", [], "degraded", ["checkout waiting on database connections"]),
 "network_latency": ("Network latency", True, dict(error_count=6,latency_ms=2200,dependency_status="slow"), ["P95 latency above threshold"], ["WARN upstream request took 2.1 seconds"], "v1.0", [], "healthy", ["checkout running; upstream calls slow"]),
 "dependency_timeout": ("Dependency timeout", True, dict(error_count=24,http_status=503,latency_ms=2500,dependency_status="timeout",queue_depth=15), ["Payment dependency timeout rate high"], ["ERROR payment provider request timed out"], "v1.0", [], "degraded", ["checkout blocked on payment dependency"]),
 "intermittent_errors": ("Intermittent errors", True, dict(error_count=9,http_status=500,latency_ms=320,dependency_status="flaky"), ["Intermittent 5xx errors"], ["ERROR intermittent payment parsing failure","INFO retry succeeded"], "v1.0", [], "healthy", ["checkout process running"]),
 "config_drift": ("Configuration drift", True, dict(error_count=17,http_status=500,latency_ms=700,container_restarts=1), ["Errors increased after config update"], ["ERROR missing CHECKOUT_TIMEOUT configuration"], "v1.0", ["CHECKOUT_TIMEOUT changed from 3s to empty"], "degraded", ["checkout running with invalid configuration"]),
 "traffic_spike": ("Traffic spike", True, dict(cpu_percent=82,memory_percent=68,error_count=11,http_status=503,latency_ms=900,queue_depth=85,traffic_rps=1200), ["Traffic rate exceeds baseline"], ["WARN request queue growing under high traffic"], "v1.0", [], "healthy", ["checkout workers busy processing backlog"]),
 "queue_backlog": ("Queue backlog", True, dict(cpu_percent=57,memory_percent=59,queue_depth=940), ["Queue depth above 900"], ["WARN background worker cannot drain queue"], "v1.0", [], "healthy", ["queue-worker active; backlog remains high"]),
 "rate_limit": ("Rate limiting", True, dict(error_count=18,http_status=429,rate_limit_count=320,traffic_rps=260), ["Rate-limit responses increased"], ["WARN checkout request rejected by rate limiter"], "v1.0", ["Rate-limit policy unchanged"], "healthy", ["checkout process running; requests throttled"]),
 "auth_failure": ("Authentication failures", True, dict(error_count=22,http_status=401,auth_failures=450), ["Authentication failure count elevated"], ["WARN repeated authentication failures","SECURITY login failure threshold exceeded"], "v1.0", [], "healthy", ["checkout process running"]),
 "certificate_expiry": ("Certificate nearing expiry", True, dict(certificate_days_remaining=2), ["TLS certificate expires in 2 days"], ["WARN TLS certificate expiration approaching"], "v1.0", [], "healthy", ["checkout process running"]),
}
SCENARIOS = {}
for key, (title, expected, overrides, alerts, logs, version, changes, health, processes) in _RAW.items():
    metrics = dict(BASE); metrics.update(overrides)
    SCENARIOS[key] = dict(title=title, description=title + " simulated fixture.", incident_expected=expected,
        metrics=metrics, alerts=alerts, logs=logs, version=version, config_changes=changes,
        container_health=health, processes=processes)

def default_state():
    s = SCENARIOS["healthy"]
    return {"scenario":"healthy","title":s["title"],"description":s["description"],"incident_expected":False,
            "metrics":dict(s["metrics"]),"alerts":list(s["alerts"]),"logs":list(s["logs"]),
            "version":s["version"],"config_changes":list(s["config_changes"]),
            "container_health":s["container_health"],"processes":list(s["processes"]),
            "pending_proposals":{},"remediation_history":[]}

def load_state():
    p=Path(STATE_FILE)
    try:
        if p.exists():
            data=json.loads(p.read_text())
            if isinstance(data,dict) and "metrics" in data: return data
    except (OSError, ValueError): pass
    return default_state()

def save_state(state):
    p=Path(STATE_FILE); p.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix="state-",suffix=".json",dir=str(p.parent))
    try:
        with os.fdopen(fd,"w") as f: json.dump(state,f,indent=2)
        os.replace(tmp,p)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def set_scenario(name):
    if name not in SCENARIOS: raise KeyError(name)
    s=SCENARIOS[name]
    state={"scenario":name,"title":s["title"],"description":s["description"],"incident_expected":s["incident_expected"],
        "metrics":dict(s["metrics"]),"alerts":list(s["alerts"]),"logs":list(s["logs"]),"version":s["version"],
        "config_changes":list(s["config_changes"]),"container_health":s["container_health"],"processes":list(s["processes"]),
        "pending_proposals":{},"remediation_history":[]}
    save_state(state); return state
