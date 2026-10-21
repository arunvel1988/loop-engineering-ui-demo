from pathlib import Path
from mcp.server.fastmcp import FastMCP
mcp=FastMCP("logs-mcp", host="0.0.0.0", port=8000)
@mcp.tool()
def search_logs(pattern: str="ERROR", limit: int=30) -> dict:
    """Search simulated application logs for a text pattern."""
    p=Path("/logs/app.log")
    lines=p.read_text().splitlines() if p.exists() else [
      "12:00:00 INFO service started",
      "12:02:00 ERROR checkout handler failed after simulated deployment",
      "12:02:05 ERROR repeated checkout timeout",
    ]
    hits=[x for x in lines if pattern.lower() in x.lower()]
    return {"pattern":pattern,"matches":hits[-max(1,min(limit,100)):],"count":len(hits),"source":"demo fixture"}
@mcp.tool()
def get_error_summary() -> dict:
    """Summarize the demo application's known errors."""
    return {"errors":["checkout handler failed after simulated deployment","repeated checkout timeout"],"timestamps":["12:02:00","12:02:05"],"note":"Synthetic training data; correlate with deployment timeline."}
if __name__=="__main__": mcp.run(transport="streamable-http")
