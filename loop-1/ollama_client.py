import json
import requests

OLLAMA_URL = "http://localhost:11434/api/chat"

MODEL = "qwen3:8b"


# ============================================================
# PLANNER PROMPT
# ============================================================

PLANNER_PROMPT = """
You are an AI Workflow Planner.

You NEVER solve the user's goal directly.

Your ONLY responsibility is deciding the NEXT action.

Available Actions

READ_EMAILS
FILTER_EMAILS
SUMMARIZE
SEND_SLACK
DONE

Workflow

If emails are not read
-> READ_EMAILS

If emails are read but not filtered
-> FILTER_EMAILS

If emails are filtered but not summarized
-> SUMMARIZE

If summary exists but not sent
-> SEND_SLACK

If Slack notification already sent
-> DONE

Never repeat completed actions.

Always read the Current Context.

Return ONLY valid JSON.

Example

{
    "thought":"Need unread emails.",
    "action":"READ_EMAILS"
}

No markdown.

No explanation.

Only JSON.
"""


# ============================================================
# ASK PLANNER
# ============================================================

def ask_planner(goal, context):

    prompt = f"""
Goal

{goal}

Current Context

{json.dumps(context, indent=2)}

What is the NEXT action?
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

    return json.loads(answer)


# ============================================================
# SUMMARIZER
# ============================================================

def summarize_emails(emails):

    prompt = f"""
You are an expert email assistant.

Summarize the following emails.

Mention

1. Important Emails
2. Urgent Emails
3. Action Items

Emails

{json.dumps(emails, indent=2)}
"""

    payload = {

        "model": MODEL,

        "messages": [

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
