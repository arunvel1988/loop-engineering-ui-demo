from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from shared_state import SCENARIOS, default_state, load_state, save_state, set_scenario
app=FastAPI(title="Simulated Checkout App")
class Simulation(BaseModel):
    scenario: str="healthy"
@app.on_event("startup")
def startup():
    save_state(load_state() or default_state())
@app.get("/")
def root():
    s=load_state(); return {"service":"simulated-checkout","scenario":s.get("scenario"),"health":s.get("container_health")}
@app.get("/health")
def health():
    s=load_state(); m=s.get("metrics",{})
    healthy=s.get("container_health")=="healthy" and m.get("http_status",200)<500
    return {"status":"healthy" if healthy else "degraded","scenario":s.get("scenario"),"http_status":m.get("http_status",200)}
@app.get("/state")
def state(): return load_state()
@app.get("/scenarios")
def scenarios():
    return {k:{"title":v["title"],"description":v["description"],"incident_expected":v["incident_expected"]} for k,v in SCENARIOS.items()}
@app.post("/simulate-incident")
def simulate(body:Simulation):
    try: s=set_scenario(body.scenario)
    except KeyError: raise HTTPException(404,detail=f"Unknown scenario {body.scenario}")
    return {"ok":True,"scenario":body.scenario,"title":s["title"],"description":s["description"],"state":s}
@app.post("/reset")
def reset(): return {"ok":True,"state":set_scenario("healthy")}
