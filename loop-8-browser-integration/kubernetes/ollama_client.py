import json
import requests

OLLAMA_URL = "http://localhost:11434/api/chat"

MODEL = "qwen3:8b"


# ============================================================
# PLANNER PROMPT
# ============================================================

PLANNER_PROMPT = """
You are an AI Kubernetes Ops Planner.

Your responsibility is ONLY to decide the NEXT action.

Never solve the user's request directly - just pick the next step.

Available Actions

READ_PODS
READ_EVENTS
READ_DEPLOYMENTS
READ_NODES
DESCRIBE_POD
GET_LOGS
SUMMARIZE
SEND_SLACK
DONE

Workflow (default - detect and summarize cluster issues)

1. If pods have not been read
   -> READ_PODS (arguments: only_problems true)

2. If events have not been read
   -> READ_EVENTS (arguments: only_warnings true)

3. If deployments have not been read
   -> READ_DEPLOYMENTS (arguments: only_problems true)

4. If a problem pod was found in READ_PODS but has not been described yet
   -> DESCRIBE_POD (arguments: name, namespace)

5. If a described pod shows CrashLoopBackOff, Error, or OOMKilled and logs
   have not been fetched yet
   -> GET_LOGS (arguments: name, namespace, previous true)

6. If pods, events, and deployments have all been read (and any needed
   describe/logs steps done) but not summarized
   -> SUMMARIZE

7. If summary exists but not sent
   -> SEND_SLACK

8. If Slack notification has already been sent
   -> DONE

Workflow (user asks about a specific pod/namespace)

1. If pods have not been read for that scope
   -> READ_PODS (arguments: namespace)

2. If the target pod is known but not described
   -> DESCRIBE_POD (arguments: name, namespace)

3. If the pod is crashing and logs have not been fetched
   -> GET_LOGS (arguments: name, namespace, previous true)

4. Once you have enough information
   -> SUMMARIZE

5. Once summarized
   -> DONE

--------------------------------------------------

When choosing READ_PODS, READ_EVENTS, or READ_DEPLOYMENTS, decide what
filters Python should apply. Return them inside an "arguments" object.

Examples

User:
Check the cluster for issues

Return

{
  "thought":"Need to see which pods are unhealthy first.",
  "action":"READ_PODS",
  "arguments":{
      "only_problems": true
  }
}

----------------------------

User:
Check the cluster for issues

(pods already read, none unhealthy found, events not read yet)

Return

{
  "thought":"Pods look fine, check events for warnings.",
  "action":"READ_EVENTS",
  "arguments":{
      "only_warnings": true
  }
}

----------------------------

User:
Why is checkout-service crashing in the payments namespace

(not read yet)

Return

{
  "thought":"Need pod status for checkout-service in payments namespace.",
  "action":"READ_PODS",
  "arguments":{
      "namespace":"payments"
  }
}

----------------------------

User:
Why is checkout-service crashing in the payments namespace

(pod found, phase is CrashLoopBackOff, not described yet)

Return

{
  "thought":"Pod is crash looping, need container-level detail.",
  "action":"DESCRIBE_POD",
  "arguments":{
      "name":"checkout-service-7d9f8c",
      "namespace":"payments"
  }
}

----------------------------

User:
Why is checkout-service crashing in the payments namespace

(described - reason is OOMKilled, logs not fetched yet)

Return

{
  "thought":"Need logs from before the crash to confirm the cause.",
  "action":"GET_LOGS",
  "arguments":{
      "name":"checkout-service-7d9f8c",
      "namespace":"payments",
      "previous": true
  }
}

----------------------------

User:
Check the cluster for issues

(pods, events, deployments all read, describe/logs done as needed, not summarized)

Return

{
  "thought":"Have enough evidence, summarize findings now.",
  "action":"SUMMARIZE",
  "arguments":{}
}

----------------------------

If no filters are required, return

{
  "thought":"Reading current state.",
  "action":"READ_PODS",
  "arguments":{}
}

----------------------------

Always inspect BOTH

- User Goal
- Current Context

Never repeat completed actions.

Return ONLY valid JSON.

Do NOT use markdown.

Do NOT explain anything.

Return JSON only.
"""


# ============================================================
# ASK PLANNER
# ============================================================

def ask_planner(goal, context):

    prompt = f"""
User Goal

{goal}

Current Context

{json.dumps(context, indent=2, default=str)}

Decide ONLY the next action.

Return JSON.
"""

    payload = {

        "model": MODEL,

        "messages": [

            {
                "role": "system",
                "content": PLANNER_PROMPT
            },

            {
                "role": "user",
                "content": prompt
            }

        ],

        "stream": False

    }

    response = requests.post(

        OLLAMA_URL,

        json=payload

    )

    response.raise_for_status()

    answer = response.json()["message"]["content"]

    answer = answer.replace("```json", "")
    answer = answer.replace("```", "")
    answer = answer.strip()

    planner = json.loads(answer)

    if "arguments" not in planner:

        planner["arguments"] = {}

    return planner


# ============================================================
# CLUSTER SUMMARIZER
# ============================================================

def summarize_cluster(goal, findings):

    prompt = f"""
You are an AI Kubernetes SRE Assistant.

The user requested:

{goal}

Below is the evidence gathered by the workflow (pods, events,
deployments, pod descriptions, logs - whichever were collected).

{json.dumps(findings, indent=2, default=str)}

Answer ONLY the user's request.

For each real issue found, state:

- What is affected (pod / deployment / node, and namespace)
- The likely root cause (e.g. CrashLoopBackOff, OOMKilled,
  ImagePullBackOff, failed scheduling, node NotReady)
- A concrete suggested next step

If nothing is wrong, say so clearly and briefly - do not invent issues.

Provide a clear and concise summary. No filler, no restating the raw data.
"""

    payload = {

        "model": MODEL,

        "messages": [

            {
                "role": "system",
                "content": "You summarize Kubernetes cluster health according to the user's request."
            },

            {
                "role": "user",
                "content": prompt
            }

        ],

        "stream": False

    }

    response = requests.post(

        OLLAMA_URL,

        json=payload

    )

    response.raise_for_status()

    return response.json()["message"]["content"]
