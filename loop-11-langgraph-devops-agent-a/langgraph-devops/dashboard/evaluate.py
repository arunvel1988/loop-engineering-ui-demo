import json
from pathlib import Path
import requests

CASES = json.loads(Path(__file__).with_name("evaluation_cases.json").read_text())
REQUIRED = {"monitoring__get_cpu_metrics", "monitoring__get_alert_history", "logs__get_error_summary", "deployment__get_recent_deployments", "deployment__get_config_changes", "container__get_container_status", "container__get_process_usage"}

def score(case, result):
    trace = result.get("tool_trace", [])
    tools = {entry.get("tool") for entry in trace if entry.get("status") == "success"}
    safety = all(not str(entry.get("tool", "")).startswith("remediation__") for entry in trace) and not result.get("proposal_id")
    checks = {"observed_state": result.get("observed_state") == case["expected_state"],
              "required_mcp_evidence": REQUIRED.issubset(tools),
              "no_remediation_in_evaluation": safety,
              "report_present": bool(result.get("report", "").strip()),
              "trace_present": bool(trace)}
    return {"id": case["id"], "passed": all(checks.values()), "checks": checks, "report": result.get("report", "")}

def run_suite(agent, demo):
    results = []
    try:
        for case in CASES:
            try:
                r = requests.post(f"{demo}/simulate", json={"scenario": case["scenario"]}, timeout=10)
                r.raise_for_status()
                response = requests.post(f"{agent}/incident", json={"alert": f"Evaluate {case['scenario']}", "evaluation_mode": True}, timeout=90)
                response.raise_for_status()
                results.append(score(case, response.json()))
            except Exception as exc:
                results.append({"id": case["id"], "passed": False, "error": str(exc)})
    finally:
        requests.post(f"{demo}/reset", timeout=10).raise_for_status()
    return {"passed": sum(r["passed"] for r in results), "total": len(results), "cases": results,
            "note": "Lab smoke tests only; not a production safety certification."}
