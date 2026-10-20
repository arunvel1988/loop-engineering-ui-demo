import os
import re
from flask import Flask, jsonify, render_template_string, request
import requests

app = Flask(__name__)

AGENT_URL = os.getenv("AGENT_URL", "http://agent:8080").rstrip("/")
DEMO_URL = os.getenv("DEMO_URL", "http://demo-app:5000").rstrip("/")
TIMEOUT = 120

PAGE = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Agentic DevOps Control Room</title>
<style>
:root {
  color-scheme: dark;
  --bg:#0b1020; --panel:#121a2b; --panel2:#172238;
  --line:#283650; --text:#edf3ff; --muted:#9aabc5;
  --blue:#72a7ff; --green:#43d9a3; --red:#ff6f7d;
  --amber:#ffc76b;
}
* { box-sizing:border-box }
body {
  margin:0; background:var(--bg); color:var(--text);
  font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif;
}
header {
  padding:20px 4%; border-bottom:1px solid var(--line);
  display:flex; justify-content:space-between; align-items:center;
  gap:12px; background:#0b1020;
}
header h1 { font-size:19px; margin:0 }
header p { color:var(--muted); font-size:12px; margin:3px 0 0 }
.wrap { max-width:1440px; margin:auto; padding:28px 4% 50px }
.hero { margin-bottom:22px }
.hero h2 { font-size:30px; margin:6px 0 }
.hero p { color:var(--muted); margin:0 }
.eyebrow { color:var(--blue); font-size:11px; letter-spacing:2px }
.grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:13px; margin:20px 0 }
.card {
  background:var(--panel); border:1px solid var(--line);
  border-radius:14px; padding:17px; min-width:0;
}
.metric-label,.sub,.note { color:var(--muted); font-size:12px }
.metric { font-size:25px; font-weight:750; margin:7px 0 }
.main-grid { display:grid; grid-template-columns:1.4fr .8fr; gap:15px }
.section-title { display:flex; justify-content:space-between; gap:10px; margin-bottom:14px }
.section-title h3 { margin:0; font-size:16px }
.section-title span { color:var(--muted); font-size:12px }
.actions { display:grid; grid-template-columns:1fr 1fr; gap:9px }
.btn {
  padding:11px 13px; border:1px solid var(--line);
  border-radius:9px; color:var(--text); background:var(--panel2);
  cursor:pointer; font-weight:700; font-size:13px;
}
.btn:hover { border-color:var(--blue) }
.btn:disabled { opacity:.55; cursor:wait }
.primary { background:#2866d8; border-color:#2866d8 }
.approve { background:#123c36; border-color:#1e7765; color:#9cf4d8 }
.danger { background:#40202b; border-color:#68303c; color:#ffb2bb }
.full { grid-column:1/-1 }
.workflow { display:flex; flex-wrap:wrap; gap:7px; margin-top:16px }
.step { padding:6px 9px; border:1px solid var(--line); border-radius:7px; font-size:11px; color:var(--muted) }
.step.active { border-color:var(--blue); color:#c7ddff }
.step.done { border-color:#236d5d; color:#9cf4d8 }
.report {
  min-height:200px; max-height:510px; overflow:auto;
  white-space:pre-wrap; overflow-wrap:anywhere;
  font:13px/1.7 ui-monospace,monospace;
  background:#090f1c; border:1px solid #202d43;
  border-radius:10px; padding:15px;
}
.empty { color:var(--muted); padding:24px; text-align:center }
.proposal {
  display:none; margin-top:14px; padding:15px;
  border:1px solid #7c6338; background:#282218; border-radius:12px;
}
.proposal h4 { margin:0 0 6px; color:#ffd58a }
.proposal p { font-size:12px; color:#d8c8a9 }
.proposal-id { font:12px ui-monospace,monospace; overflow-wrap:anywhere }
.proposal-buttons { display:flex; flex-wrap:wrap; gap:9px }
.tools,.events { display:grid; grid-template-columns:1fr 1fr; gap:10px }
.tool { padding:11px; border:1px solid var(--line); border-radius:9px }
.tool b { display:block; font-size:12px }
.tool small { color:var(--muted); font-size:11px }
.event { border-left:2px solid var(--blue); padding-left:10px; margin:10px 0; font-size:12px }
.event strong { display:block }
.event p { color:var(--muted); margin:2px 0 }
.note { margin-top:13px }
.toast {
  display:none; position:fixed; bottom:20px; right:20px;
  max-width:450px; padding:14px; border-radius:10px;
  background:#17243a; border:1px solid #3c5276; z-index:10;
}
.toast.error { border-color:var(--red) }
.footer { text-align:center; color:var(--muted); font-size:11px; margin-top:22px }
@media(max-width:900px) {
  .grid { grid-template-columns:repeat(2,minmax(0,1fr)) }
  .main-grid { grid-template-columns:1fr }
}
@media(max-width:520px) {
  .wrap { padding:20px 13px }
  .grid { gap:8px }
  .card { padding:12px }
  .actions { grid-template-columns:1fr }
  .tools { grid-template-columns:1fr 1fr }
  .hero h2 { font-size:25px }
}
</style>
</head>
<body>
<header>
  <div>
    <h1>Agentic DevOps Control Room</h1>
    <p>Groq reasoning · MCP tools · Docker incident lab</p>
  </div>
  <div id="topStatus">Connecting to services...</div>
</header>

<main class="wrap">
  <section class="hero">
    <div class="eyebrow">OPERATIONS CONSOLE / INCIDENT RESPONSE</div>
    <h2>Investigate. Decide. Recover.</h2>
    <p>Simulate an incident, investigate it with AI, and approve or reject remediation from this dashboard.</p>
  </section>

  <section class="grid">
    <div class="card">
      <div class="metric-label">Application health</div>
      <div class="metric" id="healthMetric">Checking</div>
      <div class="sub" id="healthSub">Waiting for demo app</div>
    </div>
    <div class="card">
      <div class="metric-label">Simulated CPU</div>
      <div class="metric" id="cpuMetric">—</div>
      <div class="sub">Synthetic metric</div>
    </div>
    <div class="card">
      <div class="metric-label">Deployment version</div>
      <div class="metric" id="versionMetric">—</div>
      <div class="sub" id="changeSub">Current demo configuration</div>
    </div>
    <div class="card">
      <div class="metric-label">AI agent / Groq</div>
      <div class="metric" id="agentMetric">Checking</div>
      <div class="sub" id="modelSub">Agent API status</div>
    </div>
  </section>

  <section class="main-grid">
    <div>
      <section class="card">
        <div class="section-title">
          <h3>Incident controls</h3>
          <span id="lastUpdated">Live status</span>
        </div>
        <div class="actions">
          <button class="btn primary full" id="runDemo" onclick="runDemo()">
            Simulate incident + investigate with AI
          </button>
          <button class="btn" onclick="simulateOnly()">Simulate incident only</button>
          <button class="btn" onclick="investigate()">Investigate current state</button>
          <button class="btn full" onclick="refreshStatus()">Refresh status</button>
        </div>
        <div class="workflow">
          <span class="step" id="step1">1 · Trigger</span>
          <span class="step" id="step2">2 · Investigate</span>
          <span class="step" id="step3">3 · Human review</span>
          <span class="step" id="step4">4 · Verify recovery</span>
        </div>
        <p class="note">
          This is a simulated lab. The rollback only changes the demo application's configuration.
        </p>
      </section>

      <section class="card" style="margin-top:15px">
        <div class="section-title">
          <h3>AI incident report</h3>
          <span id="reportMeta">No investigation yet</span>
        </div>
        <div id="report" class="empty">
          Click “Simulate incident + investigate with AI” to begin.
        </div>

        <!-- Human approval panel -->
        <div class="proposal" id="proposal">
          <h4>Remediation awaiting human approval</h4>
          <p id="proposalText">
            Review the proposed action before approving or rejecting it.
          </p>
          <div class="proposal-id">
            Proposal ID: <span id="proposalId">—</span>
          </div>
          <div class="proposal-buttons" style="margin-top:12px">
            <button class="btn approve" id="approveBtn"
                    onclick="approveProposal(true)">
              Approve demo rollback
            </button>
            <button class="btn danger" id="rejectBtn"
                    onclick="approveProposal(false)">
              Reject proposal
            </button>
          </div>
        </div>
      </section>
    </div>

    <div>
      <section class="card">
        <div class="section-title"><h3>Connected MCP servers</h3></div>
        <div class="tools">
          <div class="tool"><b>Monitoring</b><small>CPU / alerts</small></div>
          <div class="tool"><b>Logs</b><small>Error search</small></div>
          <div class="tool"><b>Deployment</b><small>Release history</small></div>
          <div class="tool"><b>Container</b><small>Health / status</small></div>
          <div class="tool" style="grid-column:1/-1">
            <b>Remediation</b><small>Allowlisted actions · approval required</small>
          </div>
        </div>
      </section>

      <section class="card" style="margin-top:15px">
        <div class="section-title"><h3>Activity timeline</h3></div>
        <div id="events">
          <div class="event"><strong>Dashboard ready</strong><p>Waiting for action.</p></div>
        </div>
      </section>

      <section class="card" style="margin-top:15px">
        <div class="section-title"><h3>Safety guardrails</h3></div>
        <p class="note">Investigation is read-only. The AI cannot approve its own proposal.</p>
        <p class="note">Only allowlisted demo remediation should be executable.</p>
      </section>
    </div>
  </section>
  <div class="footer">Flask dashboard · FastAPI agent · Groq · MCP · Docker Compose</div>
</main>
<div class="toast" id="toast"></div>

<script>
let currentProposal = null;
let busy = false;

function toast(message, error=false) {
    const el = document.getElementById("toast");
    el.textContent = message;
    el.className = "toast" + (error ? " error" : "");
    el.style.display = "block";
    setTimeout(() => el.style.display = "none", 6000);
}

function addEvent(title, description) {
    const container = document.getElementById("events");
    const item = document.createElement("div");
    item.className = "event";
    const strong = document.createElement("strong");
    strong.textContent = title;
    const p = document.createElement("p");
    p.textContent = description;
    item.append(strong, p);
    container.prepend(item);
    while (container.children.length > 8) {
        container.lastElementChild.remove();
    }
}

function setBusy(value, message) {
    busy = value;
    document.querySelectorAll("button").forEach(b => b.disabled = value);
    if (value) {
        const report = document.getElementById("report");
        report.className = "report";
        report.textContent = message || "Working...";
    }
}

async function api(path, body) {
    const response = await fetch(path, {
        method: body === undefined ? "GET" : "POST",
        headers: {"Content-Type": "application/json"},
        body: body === undefined ? undefined : JSON.stringify(body)
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(data.error || data.detail || response.statusText);
    }
    return data;
}

/*
 * Supports structured proposal IDs first, then extracts IDs from Markdown.
 * Handles Groq reports such as: **Proposal ID:** `1483e21e`
 */
function extractProposalId(data) {
    const proposal = data.proposal || {};
    const directId = data.proposal_id || proposal.proposal_id || proposal.id;
    if (directId) return String(directId);

    const report = data.report || "";
    const patterns = [
        /Proposal ID:\s*\*{0,2}\s*`?([a-f0-9-]{6,36})`?/i,
        /proposal_id["'\s]*[:=]["'\s]*([a-f0-9-]{6,36})/i
    ];

    for (const pattern of patterns) {
        const match = report.match(pattern);
        if (match) return match[1];
    }
    return null;
}

function showReport(data) {
    const report = document.getElementById("report");
    report.className = "report";
    report.textContent = data.report || JSON.stringify(data, null, 2);
    document.getElementById("reportMeta").textContent =
        "Model: " + (data.model || "Groq agent");

    const proposalId = extractProposalId(data);
    const panel = document.getElementById("proposal");

    if (proposalId) {
        currentProposal = proposalId;
        document.getElementById("proposalId").textContent = proposalId;

        const action = (data.proposal && data.proposal.action) || "demo rollback";
        document.getElementById("proposalText").textContent =
            "Proposed action: " + action +
            ". Review the report. No remediation executes until you approve.";

        panel.style.display = "block";
        document.getElementById("step3").className = "step active";
        addEvent("Proposal created", "Waiting for human decision: " + proposalId);
    } else {
        currentProposal = null;
        panel.style.display = "none";
        addEvent(
            "No proposal ID returned",
            "Investigation completed, but no approval ID was found. Check agent response."
        );
    }
}

async function runDemo() {
    if (busy) return;
    setBusy(true, "Simulating incident and investigating with Groq...\nPlease wait.");
    document.getElementById("step1").className = "step active";

    try {
        const data = await api("/api/run-demo", {});
        document.getElementById("step1").className = "step done";
        document.getElementById("step2").className = "step done";
        showReport(data.investigation);
        addEvent("Investigation complete", "Review the report and proposed action.");
        await refreshStatus(false);
        toast(currentProposal
            ? "Investigation complete. Human approval is available below the report."
            : "Investigation complete, but no proposal ID was returned.");
    } catch (error) {
        showError("Workflow failed: " + error.message);
    } finally {
        setBusy(false);
    }
}

async function simulateOnly() {
    if (busy) return;
    setBusy(true, "Simulating incident...");
    try {
        const data = await api("/api/simulate", {});
        addEvent("Incident simulated", data.message || "Demo app entered degraded state.");
        document.getElementById("step1").className = "step done";
        await refreshStatus(false);
        toast("Incident simulated. Click Investigate current state.");
    } catch (error) {
        toast(error.message, true);
    } finally {
        setBusy(false);
    }
}

async function investigate() {
    if (busy) return;
    setBusy(true, "Groq is investigating metrics, logs and deployment history...\nPlease wait.");
    document.getElementById("step2").className = "step active";
    try {
        const data = await api("/api/investigate", {});
        showReport(data);
        document.getElementById("step2").className = "step done";
        toast(currentProposal
            ? "Investigation complete. Review the approval panel."
            : "Investigation complete, but no proposal ID was returned.");
    } catch (error) {
        showError("Investigation failed: " + error.message);
    } finally {
        setBusy(false);
    }
}

async function approveProposal(approved) {
    if (!currentProposal) {
        toast("No pending proposal ID. Run an investigation that creates a proposal.", true);
        return;
    }
    if (busy) return;

    const proposalId = currentProposal;
    setBusy(true, approved
        ? "Executing approved demo rollback and verifying health..."
        : "Rejecting proposal...");

    try {
        const data = await api("/api/approve", {
            proposal_id: proposalId,
            approved: approved
        });

        document.getElementById("proposal").style.display = "none";
        document.getElementById("step3").className = "step done";
        currentProposal = null;

        if (approved) {
            document.getElementById("step4").className = "step active";
            addEvent("Rollback approved", "Checking application health.");
            await refreshStatus(false);
            document.getElementById("step4").className = "step done";
            addEvent(
                "Post-remediation verification",
                JSON.stringify(data.post_fix_health || data)
            );
            document.getElementById("reportMeta").textContent = "Remediation executed";
            toast("Approval submitted. Review the health status.");
        } else {
            addEvent("Proposal rejected", "No remediation was executed.");
            document.getElementById("reportMeta").textContent = "Proposal rejected";
            toast("Proposal rejected. No remediation was executed.");
        }
    } catch (error) {
        toast("Approval failed: " + error.message, true);
    } finally {
        setBusy(false);
        await refreshStatus(false);
    }
}

function showError(message) {
    const report = document.getElementById("report");
    report.className = "report";
    report.textContent = message;
    addEvent("Error", message);
    toast(message, true);
}

async function refreshStatus(showToast=true) {
    try {
        const data = await api("/api/status");
        const application = data.application || {};
        const state = data.state || {};
        const healthy = application.status === "ok";

        const health = document.getElementById("healthMetric");
        health.textContent = healthy ? "Healthy" : (application.status || "Unknown");
        health.style.color = healthy ? "var(--green)" : "var(--red)";
        document.getElementById("healthSub").textContent =
            "HTTP " + (data.health_http || "—") + " · " +
            (application.message || "Application status");

        const bad = state.incident_mode === "bad";
        const cpu = document.getElementById("cpuMetric");
        cpu.textContent = bad ? "92%" : "18%";
        cpu.style.color = bad ? "var(--red)" : "var(--green)";

        document.getElementById("versionMetric").textContent =
            state.version || application.version || "—";
        document.getElementById("changeSub").textContent =
            state.last_change || "Current demo configuration";

        const agent = document.getElementById("agentMetric");
        agent.textContent = data.agent_ok ? "Online" : "Offline";
        agent.style.color = data.agent_ok ? "var(--green)" : "var(--red)";
        document.getElementById("modelSub").textContent =
            data.model || "Agent API status";
        document.getElementById("topStatus").textContent =
            data.agent_ok ? "Agent and app reachable" : "Agent connection issue";
        document.getElementById("lastUpdated").textContent =
            "Updated " + new Date().toLocaleTimeString();

        if (showToast) toast("Status refreshed");
    } catch (error) {
        if (showToast) toast("Status refresh failed: " + error.message, true);
    }
}

refreshStatus(false);
setInterval(() => {
    if (!busy) refreshStatus(false);
}, 15000);
</script>
</body>
</html>'''


def json_get(url, timeout=5):
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    return response.json()


def extract_proposal_id(data):
    """Prefer structured IDs; fall back to Groq's Markdown report."""
    proposal = data.get("proposal") or {}
    proposal_id = (
        data.get("proposal_id")
        or proposal.get("proposal_id")
        or proposal.get("id")
    )
    if proposal_id:
        return str(proposal_id)

    report = data.get("report") or ""
    patterns = [
        r"Proposal ID:\s*\*{0,2}\s*`?([a-f0-9-]{6,36})`?",
        r'"proposal_id"\s*:\s*"([a-f0-9-]{6,36})"',
    ]
    for pattern in patterns:
        match = re.search(pattern, report, re.I)
        if match:
            return match.group(1)
    return None


def call_agent_incident():
    response = requests.post(
        f"{AGENT_URL}/incident",
        json={
            "alert": "High CPU and application errors",
            "approval_required": True,
        },
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    data["proposal_id"] = extract_proposal_id(data)
    return data


@app.get("/")
def index():
    return render_template_string(PAGE)


@app.get("/api/status")
def status():
    result = {
        "agent_ok": False,
        "application": {},
        "state": {},
        "health_http": None,
    }

    try:
        json_get(f"{AGENT_URL}/", timeout=3)
        result["agent_ok"] = True
        result["model"] = os.getenv("GROQ_MODEL", "Groq agent")
    except Exception as exc:
        result["agent_error"] = str(exc)

    try:
        result["state"] = json_get(f"{DEMO_URL}/state")
    except Exception as exc:
        result["state_error"] = str(exc)

    try:
        response = requests.get(f"{DEMO_URL}/health", timeout=4)
        result["health_http"] = response.status_code
        result["application"] = response.json()
    except Exception as exc:
        result["application"] = {
            "status": "unreachable",
            "message": str(exc),
        }

    return jsonify(result)


@app.post("/api/simulate")
def simulate():
    try:
        response = requests.post(
            f"{AGENT_URL}/simulate-incident",
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        message = (
            data.get("application", {}).get("message")
            or "Incident simulated"
        )
        return jsonify({
            "ok": True,
            "message": message,
            "result": data,
        })
    except Exception as exc:
        return jsonify(error=f"Could not simulate incident: {exc}"), 502


@app.post("/api/investigate")
def investigate():
    try:
        data = call_agent_incident()
        return jsonify(data)
    except requests.Timeout:
        return jsonify(
            error="Investigation timed out. Check agent logs and Groq connectivity."
        ), 504
    except Exception as exc:
        return jsonify(error=f"Investigation failed: {exc}"), 502


@app.post("/api/run-demo")
def run_demo():
    """One dashboard click: simulate incident, then investigate."""
    try:
        simulation_response = requests.post(
            f"{AGENT_URL}/simulate-incident",
            timeout=10,
        )
        simulation_response.raise_for_status()
        simulation_data = simulation_response.json()

        investigation_data = call_agent_incident()

        return jsonify({
            "ok": True,
            "simulation": simulation_data,
            "investigation": investigation_data,
        })
    except requests.Timeout:
        return jsonify(
            error="The workflow timed out. Check agent logs and Groq API connectivity."
        ), 504
    except Exception as exc:
        return jsonify(error=f"Incident workflow failed: {exc}"), 502


@app.post("/api/approve")
def approve():
    body = request.get_json(silent=True) or {}
    proposal_id = str(body.get("proposal_id", "")).strip()
    approved = body.get("approved") is True

    # Restrict IDs to the expected format before forwarding to the agent.
    if not re.fullmatch(r"[a-fA-F0-9-]{6,36}", proposal_id):
        return jsonify(error="A valid proposal ID is required."), 400

    try:
        response = requests.post(
            f"{AGENT_URL}/approve",
            json={
                "proposal_id": proposal_id,
                "approved": approved,
            },
            timeout=20,
        )
        data = response.json()

        if response.status_code >= 400:
            return jsonify(
                error=data.get("detail", data.get("error", response.text))
            ), response.status_code

        return jsonify(data)

    except requests.Timeout:
        return jsonify(error="Approval request timed out. Check agent logs."), 504
    except Exception as exc:
        return jsonify(error=f"Approval request failed: {exc}"), 502


if __name__ == "__main__":
    # Listen on all interfaces inside the container.
    app.run(host="0.0.0.0", port=8081)
