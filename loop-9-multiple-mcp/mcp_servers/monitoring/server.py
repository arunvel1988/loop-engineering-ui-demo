import os, httpx
from mcp.server.fastmcp import FastMCP
mcp=FastMCP("monitoring-mcp", host="0.0.0.0", port=8000)
APP=os.getenv("APP_URL","http://demo-app:5000")
@mcp.tool()
def get_alert_history() -> dict:
    """Return the simulated alert timeline and current incident state."""
    try:
        s=httpx.get(APP+"/state",timeout=3).json()
        return {"alert":"High CPU / app degraded","simulated_cpu_percent":92 if s.get("incident_mode")=="bad" else 18,"state":s,"note":"CPU is simulated for this teaching lab."}
    except Exception as e: return {"error":str(e)}
@mcp.tool()
def get_cpu_metrics(window_minutes: int=15) -> dict:
    """Get simulated CPU metric history for the requested window."""
    bad=False
    try: bad=httpx.get(APP+"/state",timeout=3).json().get("incident_mode")=="bad"
    except: pass
    return {"window_minutes":window_minutes,"samples":[{"minutes_ago":12,"cpu_percent":20},{"minutes_ago":6,"cpu_percent":48},{"minutes_ago":2,"cpu_percent":92 if bad else 22},{"minutes_ago":0,"cpu_percent":92 if bad else 18}],"simulated":True}
if __name__=="__main__": mcp.run(transport="streamable-http")
