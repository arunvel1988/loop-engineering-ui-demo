import json,os
from fastapi import FastAPI
from pydantic import BaseModel
from groq import Groq
MODEL=os.getenv("GROQ_MODEL","openai/gpt-oss-120b"); KEY=os.getenv("GROQ_API_KEY",""); llm=Groq(api_key=KEY) if KEY else None
app=FastAPI(title="Fifth Independent AI Agent: Incident Commander")
class CommandRequest(BaseModel): alert:str; diagnosis:dict; specialist_findings:dict
@app.get("/health")
def health(): return {"status":"ok","agent":"incident_commander","model":MODEL,"llm_key_configured":bool(KEY)}
@app.post("/command")
def command(req:CommandRequest):
    facts={"alert":req.alert,"deterministic_diagnosis":req.diagnosis,"specialist_findings":req.specialist_findings,"policy":"Use only evidence; explain uncertainty; do not claim remediation was performed."}
    fallback=req.diagnosis.get("root_cause","Investigation completed.")+" Evidence: "+"; ".join(req.diagnosis.get("evidence",[])[:4])+"."
    try:
        if not llm: raise RuntimeError("GROQ_API_KEY is empty")
        out=llm.chat.completions.create(model=MODEL,temperature=0.1,messages=[{"role":"system","content":"You are the fifth independent AI agent: the DevOps Incident Commander. Synthesize the four specialist agents and deterministic evidence into a concise incident report. Do not invent facts or execute remediation."},{"role":"user","content":json.dumps(facts,indent=2)}])
        return {"summary":out.choices[0].message.content or fallback,"llm_status":"available"}
    except Exception as exc: return {"summary":fallback+" Commander LLM unavailable; deterministic summary used.","llm_status":"fallback","error":f"{type(exc).__name__}: {exc}"}
