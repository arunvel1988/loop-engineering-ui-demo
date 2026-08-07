"""
agent_loop_k8s.py

Agent loop: an Ollama model investigates a Kubernetes cluster by calling
read-only k8s_tools functions, reasoning over the results, and calling
more functions as needed - until it produces a final diagnosis.

Requires: pip install ollama kubernetes
Run: ollama pull llama3.1   (or another tool-calling capable model)
"""

import json
import ollama
import k8s_tools

MODEL = "llama3.1"

# --- Tool schemas the model can choose from ---
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_pods",
            "description": "List pods, optionally filtered to a namespace or to only unhealthy pods",
            "parameters": {
                "type": "object",
                "properties": {
                    "namespace": {"type": "string", "description": "Optional namespace filter"},
                    "only_problems": {"type": "boolean", "description": "If true, only return unhealthy pods"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "describe_pod",
            "description": "Get detailed status for one pod: container states, restart reasons (CrashLoopBackOff, OOMKilled, ImagePullBackOff, etc.)",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "namespace": {"type": "string"},
                },
                "required": ["name", "namespace"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_pod_logs",
            "description": "Get recent log lines from a pod. Use previous=true to see logs from before the last crash.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "namespace": {"type": "string"},
                    "tail_lines": {"type": "integer"},
                    "previous": {"type": "boolean"},
                },
                "required": ["name", "namespace"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_events",
            "description": "List recent cluster Warning events - often the fastest way to find why something is broken",
            "parameters": {
                "type": "object",
                "properties": {
                    "namespace": {"type": "string"},
                    "only_warnings": {"type": "boolean"},
                    "max_results": {"type": "integer"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_deployments",
            "description": "List deployments and flag ones where ready replicas < desired replicas",
            "parameters": {
                "type": "object",
                "properties": {
                    "namespace": {"type": "string"},
                    "only_problems": {"type": "boolean"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_nodes",
            "description": "List cluster nodes and whether each is Ready",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_resource_usage",
            "description": "Get CPU/memory usage per pod (requires metrics-server)",
            "parameters": {
                "type": "object",
                "properties": {"namespace": {"type": "string"}},
            },
        },
    },
]

FUNCTION_MAP = {
    "list_pods": k8s_tools.list_pods,
    "describe_pod": k8s_tools.describe_pod,
    "get_pod_logs": k8s_tools.get_pod_logs,
    "get_events": k8s_tools.get_events,
    "list_deployments": k8s_tools.list_deployments,
    "list_nodes": k8s_tools.list_nodes,
    "get_resource_usage": k8s_tools.get_resource_usage,
}

SYSTEM_PROMPT = """You are a Kubernetes SRE agent. Your job is to investigate the cluster
and find real issues (crashing pods, failed deployments, unready nodes, resource
pressure). Use the available tools to gather evidence before concluding anything.

Investigation approach:
1. Start broad: list_pods(only_problems=true) and get_events(only_warnings=true) and list_deployments(only_problems=true)
2. For each problem found, dig deeper: describe_pod() to see the failure reason,
   get_pod_logs(previous=true) if it's crash-looping.
3. Only after gathering evidence, give a final summary.

When you're done, respond with a plain-text summary (no more tool calls) listing:
- Each issue found
- Which pod/deployment/node it affects
- The likely root cause
- A suggested next step
If nothing is wrong, say so clearly.
"""


def run_agent(user_goal, max_turns=10):
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_goal},
    ]

    for turn in range(max_turns):
        response = ollama.chat(model=MODEL, messages=messages, tools=TOOLS)
        msg = response["message"]
        messages.append(msg)

        if not msg.get("tool_calls"):
            print("\n=== Diagnosis ===\n", msg["content"])
            return msg["content"]

        for call in msg["tool_calls"]:
            fn_name = call["function"]["name"]
            fn_args = call["function"]["arguments"]
            print(f"\n[Turn {turn+1}] Calling: {fn_name}({fn_args})")

            fn = FUNCTION_MAP.get(fn_name)
            if not fn:
                result = {"error": f"Unknown function {fn_name}"}
            else:
                try:
                    result = fn(**fn_args)
                except Exception as e:
                    result = {"error": str(e)}

            messages.append({
                "role": "tool",
                "content": json.dumps(result, default=str)[:4000],
            })

    print("Max turns reached without a final diagnosis.")


if __name__ == "__main__":
    goal = "Investigate the cluster for any issues right now and give me a diagnosis."
    run_agent(goal)
