import json, os, uuid
from pathlib import Path
import httpx
from mcp.server.fastmcp import FastMCP
mcp=FastMCP("remediation-mcp", host="0.0.0.0", port=8000)
STATE=Path(os.getenv("STATE_DIR","/state"))
STATE.mkdir(exist_ok=True)
PROPOSALS=STATE/"proposals.json"
APP=os.getenv("APP_URL","http://demo-app:5000")
def read(): return json.loads(PROPOSALS.read_text()) if PROPOSALS.exists() else {}
def write(x): PROPOSALS.write_text(json.dumps(x))
@mcp.tool()
def propose_fix(action: str="rollback_demo_config", reason: str="Synthetic incident investigation") -> dict:
    """Create a pending human-approved remediation proposal. Does not execute changes."""
    if action not in ("rollback_demo_config","restart_demo_service"):
        return {"error":"Action not allowlisted"}
    items=read(); pid=str(uuid.uuid4())[:8]
    items[pid]={"id":pid,"action":action,"reason":reason,"status":"pending_approval"}
    write(items)
    return {"proposal_id":pid,"action":action,"reason":reason,"status":"pending_approval","approval_endpoint":"/approve","instructions":"Human must approve via the agent API before execution."}
@mcp.tool()
def execute_approved_fix(proposal_id: str, approved: bool) -> dict:
    """Execute only an allowlisted demo fix after explicit approval through the agent."""
    items=read(); p=items.get(proposal_id)
    if not p: return {"error":"Unknown proposal ID"}
    if not approved:
        p["status"]="rejected"; items[proposal_id]=p; write(items); return {"status":"rejected"}
    if p["status"]!="pending_approval": return {"error":f"Proposal is {p['status']}"}
    # In this lab, rollback is a safe call to the demo app's simulated incident reset.
    try:
        if p["action"]=="rollback_demo_config":
            r=httpx.post(APP+"/rollback",timeout=5)
            result=r.json()
        else:
            result={"note":"Restart is intentionally simulated; no real container is restarted."}
    except Exception as e:
        result={"error":str(e)}
    p["status"]="executed"; p["result"]=result; items[proposal_id]=p; write(items)
    return {"status":"executed","proposal":p,"result":result}
if __name__=="__main__": mcp.run(transport="streamable-http")
