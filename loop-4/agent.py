import json
from groq import Groq
from tools import TOOL_FUNCTIONS

client = Groq()

MODEL = "openai/gpt-oss-120b"

# Keep short-term context small.
# This is important because GPT-OSS 120B has an 8000 TPM limit
# on your current Groq tier.
MAX_SHORT_TERM_MESSAGES = 8


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "check_server",
            "description": "Check CPU, memory and disk usage of the server.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "check_processes",
            "description": "List the top processes sorted by CPU usage. Use this to identify runaway or CPU-intensive processes.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "check_ports",
            "description": "Check listening network ports on the server.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "check_docker",
            "description": "Check Docker containers and their current state.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "search_previous_incidents",
            "description": "Search previous DevOps incidents stored in the incident database. Use this during incident investigation to look for similar past incidents, previous root causes and previous remediation results. Historical incidents are supporting evidence only and must never be treated as proof of the current root cause.",
            "parameters": {
                "type": "object",
                "properties": {
                    "alertname": {
                        "type": "string",
                        "description": "Alert name such as HighCPU."
                    },
                    "severity": {
                        "type": "string",
                        "description": "Optional severity such as critical or warning."
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of previous incidents. Keep this small."
                    }
                },
                "required": []
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "terminate_process",
            "description": "Request termination of a specific process by PID when investigation shows that the process is causing the incident. This is a remediation proposal. The application intercepts this request and requires human approval before actually terminating the process.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pid": {
                        "type": "integer",
                        "description": "PID of the process that should be terminated."
                    }
                },
                "required": ["pid"]
            }
        }
    }
]


SYSTEM_PROMPT = """
You are a professional DevOps incident investigation agent.

Your job is to investigate infrastructure problems using
REAL information collected from tools.

You must behave like a production SRE.

===========================================================
CONVERSATION MEMORY
===========================================================

You may receive previous messages from the current conversation.

Use them when relevant.

For example:

User:
Check CPU.

Agent:
CPU is 40%.

User:
Check it again.

You should understand that "it" refers to CPU.

You may compare previous observations with current observations.

IMPORTANT:

Conversation memory represents previous conversation context.

It is NOT current infrastructure telemetry.

When the user asks for the current state, use the appropriate
infrastructure tool instead of trusting an old result.

===========================================================
INVESTIGATION WORKFLOW
===========================================================

1. CHECK INCIDENT HISTORY WHEN RELEVANT
2. OBSERVE CURRENT INFRASTRUCTURE
3. INVESTIGATE
4. CORRELATE EVIDENCE
5. IDENTIFY ROOT CAUSE
6. RECOMMEND REMEDIATION
7. VERIFY

===========================================================
AVAILABLE TOOLS
===========================================================

Current infrastructure:

- check_server
- check_processes
- check_ports
- check_docker

Historical incident memory:

- search_previous_incidents

Remediation:

- terminate_process

===========================================================
CURRENT TELEMETRY
===========================================================

Use current infrastructure tools to collect real data.

Do not invent:

- CPU values
- memory values
- disk values
- process names
- process IDs
- ports
- Docker containers
- service states

If the user asks:

"what is CPU now?"

call:

check_server

Do not answer using an old conversation value.

===========================================================
CPU INCIDENT
===========================================================

If server CPU is significantly elevated and a process is
using approximately 100% CPU, investigate whether that
process correlates with the elevated CPU usage.

Only request termination when current evidence supports it.

===========================================================
HISTORICAL INCIDENT MEMORY
===========================================================

Previous incidents are long-term memory.

Use search_previous_incidents when relevant.

Historical incidents are supporting evidence only.

They must never be treated as proof of the current root cause.

If historical evidence conflicts with current telemetry,
trust current telemetry.

===========================================================
ROOT CAUSE
===========================================================

Only identify a root cause when evidence supports it.

If evidence is insufficient, say:

"Root cause could not be conclusively identified from the
available telemetry."

===========================================================
REMEDIATION
===========================================================

terminate_process is destructive.

NEVER execute destructive remediation automatically.

When strong CURRENT evidence shows that a specific process
is causing the incident:

1. Explain the evidence.
2. Identify the exact PID from CURRENT telemetry.
3. Call terminate_process with that PID.

The application intercepts the call and requires human approval.

Never terminate PID 1.

Never invent a PID.

===========================================================
RESPONSE FORMAT
===========================================================

For investigations use:

Investigation Summary

Root Cause

Evidence

Historical Evidence

Recommended Remediation

Risk Assessment

Action Required

For normal conversation, answer naturally.

Keep responses concise and evidence-based.
"""


def run_agent(task, conversation_history=None):

    """
    Run GPT-OSS with short-term conversation memory.

    conversation_history should contain recent messages from
    the current conversation.
    """

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        }
    ]

    # -------------------------------------------------------
    # SHORT-TERM MEMORY
    # -------------------------------------------------------

    if conversation_history:

        recent_history = conversation_history[
            -MAX_SHORT_TERM_MESSAGES:
        ]

        for item in recent_history:

            role = item.get("role")
            content = item.get("content", "")

            if role not in ["user", "assistant"]:
                continue

            if not content:
                continue

            # Protect TPM by limiting individual memory entries.
            if len(content) > 3000:
                content = content[:3000] + "..."

            messages.append({
                "role": role,
                "content": content
            })

    # Current request
    messages.append({
        "role": "user",
        "content": task
    })

    pending_action = None

    while True:

        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            temperature=0.2,
            max_completion_tokens=2048,
            reasoning_effort="medium"
        )

        message = response.choices[0].message

        # ---------------------------------------------------
        # NO TOOL CALL
        # ---------------------------------------------------

        if not message.tool_calls:

            return {
                "response": message.content or "",
                "pending_action": pending_action
            }

        # Add assistant tool-call message
        messages.append(message)

        # ---------------------------------------------------
        # PROCESS TOOL CALLS
        # ---------------------------------------------------

        for tool_call in message.tool_calls:

            tool_name = tool_call.function.name

            try:

                arguments = json.loads(
                    tool_call.function.arguments
                )

            except json.JSONDecodeError:

                arguments = {}

            # ------------------------------------------------
            # REMEDIATION
            # ------------------------------------------------

            if tool_name == "terminate_process":

                pid = arguments.get("pid")

                if pid is None:

                    result = {
                        "success": False,
                        "requires_approval": False,
                        "error": "No PID was provided."
                    }

                else:

                    try:

                        pid = int(pid)

                    except (ValueError, TypeError):

                        result = {
                            "success": False,
                            "requires_approval": False,
                            "error": "Invalid PID."
                        }

                    else:

                        if pid == 1:

                            result = {
                                "success": False,
                                "requires_approval": False,
                                "error": "PID 1 cannot be terminated."
                            }

                        else:

                            pending_action = {
                                "tool": "terminate_process",
                                "arguments": {
                                    "pid": pid
                                },
                                "description":
                                    f"Terminate process PID {pid}"
                            }

                            result = {
                                "success": False,
                                "requires_approval": True,
                                "pid": pid,
                                "message":
                                    f"Termination of PID {pid} requires human approval."
                            }

            # ------------------------------------------------
            # NORMAL READ-ONLY TOOL
            # ------------------------------------------------

            else:

                function = TOOL_FUNCTIONS.get(tool_name)

                if not function:

                    result = {
                        "success": False,
                        "error":
                            f"Unknown tool: {tool_name}"
                    }

                else:

                    try:

                        result = function(
                            **arguments
                        )

                    except Exception as e:

                        result = {
                            "success": False,
                            "error": str(e)
                        }

            # Give tool result back to model
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(
                    result,
                    default=str
                )
            })
