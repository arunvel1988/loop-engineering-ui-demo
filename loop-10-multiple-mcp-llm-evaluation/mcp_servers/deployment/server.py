import os, httpx
from mcp.server.fastmcp import FastMCP
mcp=FastMCP("deployment-mcp", host="0.0.0.0", port=8000)
APP=os.getenv("APP_URL", "http://demo-app:5000")
def state():
    try: return httpx.get(APP+"/state", timeout=3).json()
    except Exception as e: return {"error":str(e)}
@mcp.tool()
def get_recent_deployments() -> dict:
    """Return synthetic deployment history consistent with the demo app's current state."""
    s=state(); bad=s.get("incident_mode")=="bad"
    deployments=[{"version":"v1.0","time":"11:40","status":"healthy"}]
    if bad: deployments.append({"version":"v1.1-bad","time":"12:00","status":"failing","change":"checkout configuration changed"})
    return {"deployments":deployments,"current_state":s,"source":"synthetic lab deployment history"}
@mcp.tool()
def get_config_changes() -> dict:
    """Return configuration changes for the active simulated incident, if any."""
    s=state()
    if s.get("incident_mode")!="bad": return {"changes":[],"current_state":s,"note":"No active faulty deployment in current lab state."}
    return {"changes":[{"time":"12:00","key":"checkout_mode","old":"stable","new":"faulty","deployment":"v1.1-bad"}],"current_state":s}
if __name__=="__main__": mcp.run(transport="streamable-http")
