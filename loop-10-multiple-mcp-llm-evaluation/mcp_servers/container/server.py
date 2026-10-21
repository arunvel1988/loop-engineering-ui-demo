import os, httpx
from mcp.server.fastmcp import FastMCP
mcp=FastMCP("container-mcp", host="0.0.0.0", port=8000)
APP=os.getenv("APP_URL","http://demo-app:5000")
@mcp.tool()
def get_container_status() -> dict:
    """Return simulated app-container status without Docker socket access."""
    try:
        r=httpx.get(APP+"/health",timeout=3)
        return {"container":"demo-app","reachable":True,"http_status":r.status_code,"health":r.json(),"note":"Safe app-level diagnostic; no Docker socket access."}
    except Exception as e: return {"container":"demo-app","reachable":False,"error":str(e)}
@mcp.tool()
def get_process_usage() -> dict:
    """Return synthetic process usage consistent with the demo incident state."""
    try: bad=httpx.get(APP+"/state",timeout=3).json().get("incident_mode")=="bad"
    except Exception: bad=False
    return {"processes":[{"name":"python app.py","cpu_percent":88 if bad else 8,"pid":101},{"name":"health-check","cpu_percent":2,"pid":102}],"simulated":True,"note":"Synthetic teaching data; no host process inspection is performed."}
if __name__=="__main__": mcp.run(transport="streamable-http")
