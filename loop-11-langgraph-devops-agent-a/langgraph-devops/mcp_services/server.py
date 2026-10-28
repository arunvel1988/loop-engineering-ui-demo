import json
import os
import hmac
import httpx
from mcp.server.fastmcp import FastMCP

ROLE = os.environ["ROLE"]
DEMO_URL = os.getenv("DEMO_URL", "http://demo-app:5000")
APPROVAL_SECRET = os.getenv("APPROVAL_SECRET", "")
mcp = FastMCP(f"{ROLE}-mcp", host="0.0.0.0", port=8000, streamable_http_path="/mcp", stateless_http=True, json_response=True)

def state():
    with httpx.Client(timeout=10) as client:
        r = client.get(f"{DEMO_URL}/state")
        r.raise_for_status()
        return r.json()

if ROLE == "monitoring":
    @mcp.tool()
    def get_cpu_metrics() -> dict:
        """Read-only simulated CPU metrics."""
        s = state()
        return {"cpu_percent": s["cpu"], "memory_percent": s.get("memory_percent", 0), "disk_percent": s.get("disk_percent", 0), "latency_ms": s.get("latency_ms", 0), "traffic_rps": s.get("traffic_rps", 0), "queue_depth": s.get("queue_depth", 0), "dependency_status": s.get("dependency_status", "unknown"), "auth_failures": s.get("auth_failures", 0), "certificate_days_remaining": s.get("certificate_days_remaining", 999), "container_restarts": s.get("container_restarts", 0), "rate_limit_count": s.get("rate_limit_count", 0), "http_status": s["http_status"], "error_count": s["error_count"]}

    @mcp.tool()
    def get_alert_history() -> dict:
        """Read-only simulated alert history."""
        s = state()
        return {"alerts": s.get("alert_override") or ([] if s["health"] == "ok" else [f"{s['scenario']} detected"]), "status": s["health"], "scenario": s["scenario"]}

elif ROLE == "logs":
    @mcp.tool()
    def search_logs(query: str = "") -> dict:
        """Search simulated application logs without modifying them."""
        logs = state()["logs"]
        return {"lines": [line for line in logs if query.lower() in line.lower()]}

    @mcp.tool()
    def get_error_summary() -> dict:
        """Read-only simulated error count and messages."""
        s = state()
        return {"error_count": s["error_count"], "errors": [x for x in s["logs"] if "ERROR" in x]}

elif ROLE == "deployment":
    @mcp.tool()
    def get_recent_deployments() -> dict:
        """Read-only recent deployment history."""
        s = state()
        return {"version": s["version"], "deployments": s["deployments"]}

    @mcp.tool()
    def get_config_changes() -> dict:
        """Read-only recent configuration changes."""
        s = state()
        return {"changes": s["config_changes"], "scenario": s["scenario"]}

elif ROLE == "container":
    @mcp.tool()
    def get_container_status() -> dict:
        """Read-only simulated container and HTTP health."""
        s = state()
        return {"health": {"status": s["health"]}, "http_status": s["http_status"], "version": s["version"], "container_restarts": s.get("container_restarts", 0), "memory_percent": s.get("memory_percent", 0), "disk_percent": s.get("disk_percent", 0)}

    @mcp.tool()
    def get_process_usage() -> dict:
        """Read-only simulated process usage."""
        return {"processes": state()["processes"]}

elif ROLE == "remediation":
    @mcp.tool()
    def propose_fix(action: str, reason: str) -> dict:
        """Create a text-only proposal; does not change the application."""
        return {"action": action, "reason": reason, "status": "proposal_only", "requires_human_approval": True}

    @mcp.tool()
    def execute_approved_fix(action: str, approval_secret: str) -> dict:
        """Demo-only approved restoration. Requires independently supplied shared secret."""
        if not APPROVAL_SECRET or not hmac.compare_digest(approval_secret, APPROVAL_SECRET):
            return {"status": "denied", "reason": "Invalid approval credential"}
        if action != "restore_demo":
            return {"status": "denied", "reason": "Only restore_demo is supported"}
        with httpx.Client(timeout=10) as client:
            r = client.post(f"{DEMO_URL}/internal/restore")
            r.raise_for_status()
            return {"status": "executed", "action": action, "health": r.json()["health"]}
else:
    raise RuntimeError(f"Unknown role {ROLE}")

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
