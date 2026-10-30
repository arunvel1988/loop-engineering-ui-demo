import os, uuid
from typing import Any
from mcp.server.fastmcp import FastMCP
from shared_state import load_state, save_state
SERVICE=os.getenv("MCP_SERVICE","monitoring").lower()
mcp=FastMCP(f"{SERVICE}-mcp", host="0.0.0.0", port=8000)
def state(): return load_state()

if SERVICE=="monitoring":
    @mcp.tool()
    def get_cpu_metrics()->dict[str,Any]:
        """Read simulated CPU, memory, disk, HTTP, latency and dependency metrics."""
        return state().get("metrics",{})
    @mcp.tool()
    def get_alert_history()->dict[str,Any]:
        """Read alert signals for the simulated service."""
        s=state(); return {"scenario":s.get("scenario"),"status":s.get("container_health"),"alerts":s.get("alerts",[])}
elif SERVICE=="logs":
    @mcp.tool()
    def get_error_summary()->dict[str,Any]:
        """Read simulated error count and log lines."""
        s=state(); logs=s.get("logs",[])
        return {"error_count":s.get("metrics",{}).get("error_count",0),"errors":[x for x in logs if any(t in x.upper() for t in ["ERROR","FAIL","SECURITY"])],"logs":logs}
    @mcp.tool()
    def search_logs(query:str="")->dict[str,Any]:
        """Search simulated logs for a phrase."""
        logs=state().get("logs",[])
        return {"query":query,"matches":[x for x in logs if not query or query.lower() in x.lower()]}
elif SERVICE=="deployment":
    @mcp.tool()
    def get_recent_deployments()->dict[str,Any]:
        """Read current simulated deployed version."""
        s=state(); return {"version":s.get("version"),"deployments":[f'{s.get("version")} deployment']}
    @mcp.tool()
    def get_config_changes()->dict[str,Any]:
        """Read simulated configuration changes."""
        s=state(); return {"scenario":s.get("scenario"),"changes":s.get("config_changes",[])}
elif SERVICE=="container":
    @mcp.tool()
    def get_container_status()->dict[str,Any]:
        """Read simulated checkout container health and resource information."""
        s=state(); m=s.get("metrics",{})
        return {"health":{"status":s.get("container_health")},"http_status":m.get("http_status"),
            "container_restarts":m.get("container_restarts"),"cpu_percent":m.get("cpu_percent"),
            "memory_percent":m.get("memory_percent"),"disk_percent":m.get("disk_percent"),"version":s.get("version")}
    @mcp.tool()
    def get_process_usage()->dict[str,Any]:
        """Read simulated process descriptions; does not inspect real host processes."""
        return {"processes":state().get("processes",[])}
elif SERVICE=="remediation":
    @mcp.tool()
    def propose_fix(scenario:str,root_cause:str,recommended_action:str)->dict[str,Any]:
        """Create a proposal only; never execute a fix."""
        s=state(); pid=str(uuid.uuid4())
        proposal={"proposal_id":pid,"scenario":scenario,"root_cause":root_cause,"recommended_action":recommended_action,"status":"pending_human_approval"}
        s.setdefault("pending_proposals",{})[pid]=proposal; save_state(s); return proposal
    @mcp.tool()
    def execute_approved_fix(proposal_id:str,approved:bool)->dict[str,Any]:
        """Simulated remediation only. Agent API must validate approval secret first."""
        s=state(); pending=s.setdefault("pending_proposals",{}); p=pending.get(proposal_id)
        if not p: return {"ok":False,"message":"Unknown or expired proposal ID"}
        if not approved:
            pending.pop(proposal_id,None); s.setdefault("remediation_history",[]).append({"proposal_id":proposal_id,"status":"rejected"}); save_state(s)
            return {"ok":True,"status":"rejected","message":"No simulated state changed."}
        before=s.get("scenario")
        s["container_health"]="healthy"; s["metrics"]["http_status"]=200; s["metrics"]["error_count"]=0; s["metrics"]["container_restarts"]=0
        s["alerts"]=[]; s["logs"]=["INFO demo remediation applied; simulated checkout healthy"]; s["processes"]=["checkout process running; uptime 1 minute"]
        pending.pop(proposal_id,None); s.setdefault("remediation_history",[]).append({"proposal_id":proposal_id,"scenario_before":before,"status":"approved_and_simulated"})
        save_state(s)
        return {"ok":True,"status":"approved_and_simulated","scenario_before":before,"message":"Only simulator state changed; no real infrastructure changed."}
else:
    raise RuntimeError(f"Unknown MCP_SERVICE={SERVICE!r}")

if __name__=="__main__":
    mcp.run(transport="streamable-http")
