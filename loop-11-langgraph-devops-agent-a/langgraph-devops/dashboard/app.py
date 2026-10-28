import os
import requests
from flask import Flask, render_template_string, request

app = Flask(__name__)
AGENT = os.getenv("AGENT_URL", "http://agent:8080")
DEMO = os.getenv("DEMO_URL", "http://demo-app:5000")
SECRET = os.getenv("APPROVAL_SECRET", "")
TEMPLATE = '''<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>LangGraph DevOps Lab</title><style>
body{font-family:system-ui;background:#101725;color:#e9eef7;margin:0}main{max-width:1100px;margin:auto;padding:26px}h1{color:#8ab4ff}.card{background:#1b2639;padding:22px;margin:16px 0;border-radius:12px}button,select,input{padding:10px;margin:5px;border-radius:7px;border:0}button{background:#73aaff;color:#081426;cursor:pointer;font-weight:bold}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#101725;padding:16px;border-radius:8px}a{color:#9fc1ff}label{display:block;margin-top:8px}small{color:#b6c4d9}.grid{display:grid;grid-template-columns:1fr 1fr;gap:15px}@media(max-width:700px){.grid{grid-template-columns:1fr}}</style></head><body><main>
<h1>LangGraph DevOps Incident Lab</h1><p>Simulate incidents, investigate with MCP + Groq, and review human-approved demo restoration.</p>
{% if error %}<div class="card"><strong>Error:</strong> {{error}}</div>{% endif %}
<div class="grid"><div class="card"><h2>1. Simulate</h2><form method="post" action="/simulate"><select name="scenario">{% for s in scenarios %}<option value="{{s}}">{{s.replace("_", " ").title()}}</option>{% endfor %}</select><button>Simulate incident</button><p><small>Choose from 17 scenarios, including CPU, memory, disk, latency, dependency, configuration, traffic, authentication, queue, TLS, container and stale-alert cases.</small></p></form><form method="post" action="/reset"><button>Reset healthy</button></form></div>
<div class="card"><h2>Current state</h2><pre>{{current|tojson(indent=2)}}</pre></div></div>
<div class="card"><h2>2. Investigate</h2><form method="post" action="/investigate"><label>Alert message <input name="alert" value="Checkout service degraded" style="width:70%"></label><button>Run LangGraph investigation</button></form></div>
{% if result %}<div class="card"><h2>Investigation report</h2><pre>{{result.report}}</pre><h3>LangGraph / MCP tool trace</h3><pre>{{result.tool_trace|tojson(indent=2)}}</pre><h3>Diagnosis</h3><pre>{{result.diagnosis|tojson(indent=2)}}</pre>{% if result.proposal_id %}<h3>3. Human approval (demo only)</h3><p>Proposed action: {{result.proposal.action}}. No action has executed.</p><form method="post" action="/approve"><input type="hidden" name="proposal_id" value="{{result.proposal_id}}"><button name="approved" value="true">Approve demo restore</button><button name="approved" value="false">Reject</button></form>{% endif %}</div>{% endif %}
{% if approval %}<div class="card"><h2>Approval result</h2><pre>{{approval|tojson(indent=2)}}</pre></div>{% endif %}
<div class="card"><h2>4. Evaluation</h2><p>Runs 17 read-only evaluation cases, including healthy/stale-alert controls and 15 active incident patterns. Resets the demo between cases.</p><form method="post" action="/evaluate"><button>Run evaluation suite</button></form>{% if evaluation %}<pre>{{evaluation|tojson(indent=2)}}</pre>{% endif %}</div>
<small>Demo lab only. Production mode must be isolated and read-only; do not expose this dashboard or demo remediation service publicly.</small></main></body></html>'''

def api(method, url, **kwargs):
    r = requests.request(method, url, timeout=90, **kwargs)
    r.raise_for_status()
    return r.json()

def page(**kwargs):
    try:
        current = api("GET", f"{DEMO}/state")
        scenarios = api("GET", f"{DEMO}/scenarios")
    except Exception as exc:
        current, scenarios = {"error": str(exc)}, []
    return render_template_string(TEMPLATE, current=current, scenarios=scenarios, **kwargs)

@app.get("/")
def home():
    return page()

@app.post("/simulate")
def simulate():
    try:
        api("POST", f"{DEMO}/simulate", json={"scenario": request.form["scenario"]})
        return page()
    except Exception as exc:
        return page(error=str(exc))

@app.post("/reset")
def reset():
    try:
        api("POST", f"{DEMO}/reset")
        return page()
    except Exception as exc:
        return page(error=str(exc))

@app.post("/investigate")
def investigate():
    try:
        result = api("POST", f"{AGENT}/incident", json={"alert": request.form.get("alert", "Checkout degraded")})
        return page(result=result)
    except Exception as exc:
        return page(error=str(exc))

@app.post("/approve")
def approve():
    try:
        result = api("POST", f"{AGENT}/approve", headers={"X-Approval-Secret": SECRET}, json={"proposal_id": request.form["proposal_id"], "approved": request.form["approved"] == "true"})
        return page(approval=result)
    except Exception as exc:
        return page(error=str(exc))

@app.post("/evaluate")
def evaluate():
    from dashboard.evaluate import run_suite
    try:
        return page(evaluation=run_suite(AGENT, DEMO))
    except Exception as exc:
        return page(error=str(exc))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8081)
