from mcp.server.fastmcp import FastMCP
mcp=FastMCP("deployment-mcp", host="0.0.0.0", port=8000)
@mcp.tool()
def get_recent_deployments() -> dict:
    """Return synthetic deployment history for correlation."""
    return {"deployments":[{"version":"v1.0","time":"11:40","status":"healthy"},{"version":"v1.1-bad","time":"12:00","status":"simulated","change":"checkout configuration changed"}],"note":"Deployment history is synthetic for this Docker lab."}
@mcp.tool()
def get_config_changes() -> dict:
    """Return recent synthetic configuration changes."""
    return {"changes":[{"time":"12:00","key":"checkout_mode","old":"stable","new":"faulty","deployment":"v1.1-bad"}]}
if __name__=="__main__": mcp.run(transport="streamable-http")
