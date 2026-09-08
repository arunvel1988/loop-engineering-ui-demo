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
DRAFT_REPLY
SEND_REPLY
SEND_EMAIL
TRASH_EMAIL
MARK_AS_READ
SEND_SLACK
DONE

Workflow (default - summarizing / notifying)

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

Workflow (replying to an email)

1. If emails have not been read
   -> READ_EMAILS

2. If emails are available but not filtered and the user referred to a
   specific email by sender/subject/keyword
   -> FILTER_EMAILS

3. If the target email is known but no draft has been written yet
   -> DRAFT_REPLY (arguments: email_id, instructions)

4. If a draft exists for the target email but it has not been sent
   -> SEND_REPLY (arguments: email_id)

5. If the reply has been sent
   -> DONE

Workflow (composing a brand-new email, not a reply)

1. If you already have enough information (to, subject, body) from the
   user goal
   -> SEND_EMAIL

2. If sent
   -> DONE

Workflow (trashing or marking an email)

1. If emails have not been read
   -> READ_EMAILS

2. If emails are available but not filtered and the user referred to a
   specific email
   -> FILTER_EMAILS

3. Once the target email is identified
   -> TRASH_EMAIL or MARK_AS_READ (arguments: email_id)

4. Once done
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

----------------------------

User:
Reply to the email from my boss about Q3 numbers

(emails already read and filtered, target email id is "1")

Return

{
  "thought":"Target email identified, need to draft a reply.",
  "action":"DRAFT_REPLY",
  "arguments":{
      "email_id":"1",
      "instructions":"Confirm the Q3 numbers will be sent by EOD, professional tone."
  }
}

----------------------------

User:
Reply to the email from my boss about Q3 numbers

(draft already exists for email id "1")

Return

{
  "thought":"Draft is ready, send the reply now.",
  "action":"SEND_REPLY",
  "arguments":{
      "email_id":"1"
  }
}

----------------------------

User:
Send an email to jane@company.com telling her the report is delayed by a day

Return

{
  "thought":"Have enough info to compose a new email directly.",
  "action":"SEND_EMAIL",
  "arguments":{
      "to":"jane@company.com",
      "subject":"Report Delay",
      "body":"Hi Jane, just a heads up that the report will be delayed by a day. Thanks for your patience."
  }
}

----------------------------

User:
Delete the newsletter email

(target email id is "2")

Return

{
  "thought":"Target email identified, move it to trash.",
  "action":"TRASH_EMAIL",
  "arguments":{
      "email_id":"2"
  }
}

----------------------------

User:
Mark the client email as read

(target email id is "3")

Return

{
  "thought":"Target email identified, mark it as read.",
  "action":"MARK_AS_READ",
  "arguments":{
      "email_id":"3"
  }
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


# ============================================================
# DRAFT REPLY
# ============================================================

def draft_reply(goal, email, instructions=""):

    prompt = f"""
You are an AI Email Assistant.

The user requested:

{goal}

Write a reply to this email.

From: {email.get("from")}
Subject: {email.get("subject")}
Body: {email.get("body")}

Extra instructions:

{instructions if instructions else "None - use a professional, concise tone."}

Return ONLY the reply body text.

Do not include a subject line.

Do not include any preamble such as "Here is the reply".
"""

    payload = {

        "model": MODEL,

        "messages": [

            {
                "role": "system",
                "content": "You draft email replies according to the user's request."
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

    return response.json()["message"]["content"].strip()
