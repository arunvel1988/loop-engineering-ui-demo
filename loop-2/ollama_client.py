import json
import requests

OLLAMA_URL = "http://localhost:11434/api/chat"

MODEL = "qwen3:8b"


# ============================================================
# PLANNER PROMPT
# ============================================================

PLANNER_PROMPT = """
You are an AI Workflow Planner.

Your responsibility is ONLY to decide the NEXT action.

Never solve the user's request.

Available Actions

READ_EMAILS
FILTER_EMAILS
SUMMARIZE
SEND_SLACK
DONE

Workflow

1. If emails have not been read
   -> READ_EMAILS

2. If emails are available but not filtered
   -> FILTER_EMAILS

3. If emails are filtered but not summarized
   -> SUMMARIZE

4. If summary exists but not sent
   -> SEND_SLACK

5. If Slack notification has already been sent
   -> DONE

--------------------------------------------------

When choosing FILTER_EMAILS, determine how Python
should filter the emails.

Return any required filters inside an "arguments"
object.

Examples

User:
Show important emails

Return

{
  "thought":"Need important emails.",
  "action":"FILTER_EMAILS",
  "arguments":{
      "priority":"HIGH"
  }
}

----------------------------

User:
Show least important emails

Return

{
  "thought":"Need low priority emails.",
  "action":"FILTER_EMAILS",
  "arguments":{
      "priority":"LOW"
  }
}

----------------------------

User:
Show medium priority emails

Return

{
  "thought":"Need medium priority emails.",
  "action":"FILTER_EMAILS",
  "arguments":{
      "priority":"MEDIUM"
  }
}

----------------------------

User:
Show invoice emails

Return

{
  "thought":"Need invoice emails.",
  "action":"FILTER_EMAILS",
  "arguments":{
      "keyword":"invoice"
  }
}

----------------------------

User:
Show Microsoft emails

Return

{
  "thought":"Need Microsoft emails.",
  "action":"FILTER_EMAILS",
  "arguments":{
      "sender":"microsoft.com"
  }
}

----------------------------

User:
Show unread AWS billing emails

Return

{
  "thought":"Need AWS billing emails.",
  "action":"FILTER_EMAILS",
  "arguments":{
      "sender":"amazon.com",
      "keyword":"billing"
  }
}

----------------------------

If no filters are required, return

{
  "thought":"Need to filter emails.",
  "action":"FILTER_EMAILS",
  "arguments":{}
}

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

{json.dumps(context, indent=2)}

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

    # Ensure arguments always exists

    if "arguments" not in planner:

        planner["arguments"] = {}

    return planner


# ============================================================
# EMAIL SUMMARIZER
# ============================================================

def summarize_emails(goal, emails):

    prompt = f"""
You are an AI Email Assistant.

The user requested:

{goal}

Below are the emails selected by the workflow.

{json.dumps(emails, indent=2)}

Answer ONLY the user's request.

Do not always talk about important emails.

If the user requested:

- least important emails
- important emails
- invoice emails
- Microsoft emails
- AWS emails
- emails requiring action
- emails requiring no action

respond accordingly.

Provide a clear and concise summary.
"""

    payload = {

        "model": MODEL,

        "messages": [

            {
                "role": "system",
                "content": "You summarize emails according to the user's request."
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
