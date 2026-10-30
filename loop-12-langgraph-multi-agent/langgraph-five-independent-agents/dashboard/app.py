import os, requests
from flask import Flask, jsonify, render_template, request
app=Flask(__name__)
AGENT_URL=os.getenv("AGENT_URL","http://localhost:8080")
APP_URL=os.getenv("APP_URL","http://localhost:5000")
APPROVAL_SECRET=os.getenv("APPROVAL_SECRET","")

@app.get("/")
def index():
    try: scenarios=requests.get(f"{APP_URL}/scenarios",timeout=4).json()
    except Exception: scenarios={}
    return render_template("index.html",scenarios=scenarios)

@app.get("/api/health")
def health():
    out={}
    for name,url in [("agent",f"{AGENT_URL}/health"),("demo",f"{APP_URL}/health")]:
        try: out[name]=requests.get(url,timeout=4).json()
        except Exception as e: out[name]={"status":"unavailable","error":str(e)}
    return jsonify(out)

@app.post("/api/simulate")
def simulate():
    data=request.get_json(silent=True) or {}
    try:
        r=requests.post(f"{APP_URL}/simulate-incident",json={"scenario":data.get("scenario","healthy")},timeout=8)
        return (r.text,r.status_code,{"Content-Type":"application/json"})
    except Exception as e: return jsonify({"error":str(e)}),502

@app.post("/api/investigate")
def investigate():
    data=request.get_json(silent=True) or {}
    try:
        r=requests.post(f"{AGENT_URL}/incident",json={"alert":data.get("alert","Investigate checkout"),"evaluation_mode":False},timeout=240)
        return (r.text,r.status_code,{"Content-Type":"application/json"})
    except Exception as e: return jsonify({"error":str(e)}),502

@app.post("/api/approve")
def approve():
    data=request.get_json(silent=True) or {}
    if not data.get("proposal_id"): return jsonify({"error":"proposal_id required"}),400
    try:
        r=requests.post(f"{AGENT_URL}/approve",json={"proposal_id":data["proposal_id"],"approved":bool(data.get("approved",False))},
            headers={"X-Approval-Secret":APPROVAL_SECRET},timeout=30)
        return (r.text,r.status_code,{"Content-Type":"application/json"})
    except Exception as e: return jsonify({"error":str(e)}),502

@app.post("/api/evaluate")
def evaluate():
    try:
        r=requests.post(f"{AGENT_URL}/evaluate",timeout=900)
        return (r.text,r.status_code,{"Content-Type":"application/json"})
    except Exception as e: return jsonify({"error":str(e)}),502

if __name__=="__main__":
    app.run(host=os.getenv("FLASK_HOST","0.0.0.0"),port=int(os.getenv("FLASK_PORT","8081")),debug=False)
