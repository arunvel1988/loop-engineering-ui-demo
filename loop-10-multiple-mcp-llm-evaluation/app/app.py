import json, os, time
from pathlib import Path
from flask import Flask, jsonify
app = Flask(__name__)
LOG_DIR = Path("/logs")
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "app.log"
STATE_DIR = Path("/state")
STATE_DIR.mkdir(exist_ok=True)
STATE_FILE = STATE_DIR / "deployment.json"
if not STATE_FILE.exists():
    STATE_FILE.write_text(json.dumps({"version":"v1.0","last_change":"initial baseline","incident_mode":"normal"}))
def log(msg):
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} {msg}"
    with LOG_FILE.open("a") as f: f.write(line + "\n")
@app.get("/")
def home():
    state = json.loads(STATE_FILE.read_text())
    if state.get("incident_mode") == "bad":
        log("ERROR checkout handler failed after simulated deployment")
        return jsonify(status="degraded", message="simulated checkout error", version=state["version"]), 500
    log("INFO health request successful")
    return jsonify(status="ok", message="demo application healthy", version=state["version"])
@app.get("/health")
def health():
    state = json.loads(STATE_FILE.read_text())
    return jsonify(status="ok" if state.get("incident_mode") != "bad" else "degraded", version=state["version"]), (200 if state.get("incident_mode") != "bad" else 503)
@app.get("/logs")
def logs():
    return jsonify(lines=LOG_FILE.read_text().splitlines()[-100:] if LOG_FILE.exists() else [])
@app.get("/state")
def state():
    return jsonify(json.loads(STATE_FILE.read_text()))
@app.post("/rollback")
def rollback():
    state = json.loads(STATE_FILE.read_text())
    state.update({"version":"v1.0","last_change":"rollback to known-good demo config","incident_mode":"normal"})
    STATE_FILE.write_text(json.dumps(state))
    log("INFO simulated rollback completed")
    return jsonify(ok=True, message="Demo rollback completed", state=state)
@app.post("/simulate-incident")
def incident():
    # Demo-only incident switch. Persisted by the separate remediation volume in MCP server.
    state = json.loads(STATE_FILE.read_text())
    state.update({"version":"v1.1-bad","last_change":"simulated deployment introduced checkout error","incident_mode":"bad"})
    STATE_FILE.write_text(json.dumps(state))
    log("ERROR simulated bad deployment enabled")
    return jsonify(ok=True, message="Incident simulated", state=state)

@app.post("/reset-lab")
def reset_lab():
    """Reset this disposable teaching lab to a clean, healthy state for repeatable evaluation."""
    STATE_FILE.write_text(json.dumps({"version":"v1.0","last_change":"evaluation baseline reset","incident_mode":"normal"}))
    LOG_FILE.write_text("")
    log("INFO evaluation baseline reset; application healthy")
    return jsonify(ok=True, message="Lab reset to healthy baseline", state=json.loads(STATE_FILE.read_text()))

if __name__ == "__main__":
    # For demo simplicity app state/logs are in the container; MCP servers use their own simulated evidence fixtures.
    app.run(host="0.0.0.0", port=5000)
