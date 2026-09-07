import json
from groq import Groq

from tools import TOOL_FUNCTIONS


client = Groq()

MODEL = "openai/gpt-oss-120b"


TOOLS = [

    {
        "type": "function",

        "function": {

            "name": "check_server",

            "description":
                "Check CPU, memory and disk usage of the server.",

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

            "description":
                "List the top processes sorted by CPU usage.",

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

            "description":
                "Check listening network ports on the server.",

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

            "description":
                "Check Docker containers running on the server.",

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

            "name": "terminate_process",

            "description":
                "Terminate a specific process by PID. "
                "This is a remediation action. "
                "Never execute this automatically. "
                "Request user approval first.",

            "parameters": {

                "type": "object",

                "properties": {

                    "pid": {
                        "type": "integer",
                        "description": "PID of the process to terminate."
                    }

                },

                "required": ["pid"]
            }
        }
    }

]


SYSTEM_PROMPT = """

You are VASS DevOps Agent.

You are an infrastructure investigation and remediation agent.

Your workflow is:

1. OBSERVE
2. INVESTIGATE
3. ANALYZE
4. IDENTIFY ROOT CAUSE
5. RECOMMEND REMEDIATION
6. VERIFY

Use tools to collect real infrastructure information.

Never invent CPU, memory, process, Docker or port information.

Use multiple investigation tools when necessary.

IMPORTANT REMEDIATION RULE:

terminate_process is a destructive remediation tool.

NEVER execute terminate_process automatically.

When you determine that a process should be terminated:

- identify the PID
- explain why it should be terminated
- request user approval
- do NOT actually terminate it

The application will handle the approval.

After a remediation has been approved and executed,
investigate the system again to verify whether the incident
has been resolved.

"""


def run_agent(task):

    messages = [

        {
            "role": "system",
            "content": SYSTEM_PROMPT
        },

        {
            "role": "user",
            "content": task
        }

    ]

    pending_action = None

    while True:

        response = client.chat.completions.create(

            model=MODEL,

            messages=messages,

            tools=TOOLS,

            tool_choice="auto",

            temperature=0.2,

            max_completion_tokens=4096,

            reasoning_effort="medium"

        )

        message = response.choices[0].message

        # -------------------------------------------------
        # FINAL RESPONSE
        # -------------------------------------------------

        if not message.tool_calls:

            return {

                "response": message.content,

                "pending_action": pending_action

            }

        # Add assistant's tool request
        messages.append(message)

        # -------------------------------------------------
        # TOOL EXECUTION
        # -------------------------------------------------

        for tool_call in message.tool_calls:

            tool_name = tool_call.function.name

            arguments = json.loads(
                tool_call.function.arguments
            )

            # ---------------------------------------------
            # REMEDIATION
            # ---------------------------------------------

            if tool_name == "terminate_process":

                pid = arguments.get("pid")

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
                        f"Termination of PID {pid} requires user approval."

                }

            # ---------------------------------------------
            # NORMAL OBSERVATION TOOL
            # ---------------------------------------------

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

                        result = function(**arguments)

                    except Exception as e:

                        result = {

                            "success": False,

                            "error": str(e)

                        }

            # ---------------------------------------------
            # SEND TOOL RESULT BACK TO MODEL
            # ---------------------------------------------

            messages.append({

                "role": "tool",

                "tool_call_id": tool_call.id,

                "content": json.dumps(
                    result,
                    default=str
                )

            })
