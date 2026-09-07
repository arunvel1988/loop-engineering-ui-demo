from groq import Groq
import json

from tools import TOOL_FUNCTIONS


client = Groq()

MODEL = "openai/gpt-oss-120b"


# ============================================================
# TOOL DEFINITIONS
# ============================================================

TOOLS = [

    {
        "type": "function",

        "function": {

            "name":
                "check_server",

            "description":
                """
                Check overall server health including
                CPU usage, memory usage, disk usage,
                hostname and available memory.

                Use this when investigating server
                performance or resource problems.
                """,

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

            "name":
                "check_processes",

            "description":
                """
                Inspect running processes and identify
                processes consuming high CPU or memory.

                Use this when investigating high CPU,
                high memory or server performance issues.
                """,

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

            "name":
                "check_ports",

            "description":
                """
                Inspect network ports currently listening
                on the server.

                Use this when investigating network,
                application availability or service issues.
                """,

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

            "name":
                "check_docker",

            "description":
                """
                Inspect Docker containers and their
                current status.

                Use this when investigating container
                or application problems.
                """,

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

            "name":
                "terminate_process",

            "description":
                """
                TERMINATE a running process by PID.

                This is a destructive remediation action.

                NEVER call this automatically.

                Only call this when the user has explicitly
                approved terminating the specific PID.

                The PID must have already been identified
                as problematic during investigation.
                """,

            "parameters": {

                "type": "object",

                "properties": {

                    "pid": {

                        "type":
                            "integer",

                        "description":
                            "PID of the process to terminate"
                    }
                },

                "required": [
                    "pid"
                ]
            }
        }
    }
]


# ============================================================
# SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """

You are VASS DevOps Agent.

You are an AI agent responsible for
investigating infrastructure and
application incidents.

Your workflow is:

OBSERVE
INVESTIGATE
ANALYZE
IDENTIFY ROOT CAUSE
RECOMMEND REMEDIATION
VERIFY

You have access to real infrastructure
tools.

IMPORTANT:

Never invent infrastructure information.

When investigating a problem, use tools
to obtain real information.

You can use multiple tools during a
single investigation.

For example, if the user reports that
the server is slow:

1. Check server health.
2. Check running processes.
3. Check Docker.
4. Check network ports if necessary.
5. Correlate the evidence.
6. Identify the most likely root cause.
7. Recommend remediation.

REMEMBER:

Observation tools can be executed whenever
necessary.

Remediation tools are different.

NEVER execute a destructive remediation
automatically.

Before using terminate_process, the user
must explicitly approve terminating that
specific PID.

If remediation is required but approval
has not been given:

DO NOT execute the remediation.

Instead explain:

- Root cause
- Evidence
- Recommended action
- Risk
- Exact action requiring approval

After an approved remediation is executed,
verify the result using observation tools.

Be concise but provide enough technical
evidence for a DevOps engineer.
"""


# ============================================================
# AGENT
# ============================================================

def run_agent(task):

    messages = [

        {
            "role":
                "system",

            "content":
                SYSTEM_PROMPT
        },

        {
            "role":
                "user",

            "content":
                task
        }
    ]


    # ========================================================
    # AGENT LOOP
    # ========================================================

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


        # ====================================================
        # NO TOOL CALL
        # ====================================================

        if not message.tool_calls:

            return {

                "response":
                    message.content
            }


        # ====================================================
        # ADD MODEL MESSAGE
        # ====================================================

        messages.append(message)


        # ====================================================
        # EXECUTE REQUESTED TOOLS
        # ====================================================

        for tool_call in message.tool_calls:

            tool_name = tool_call.function.name


            # -----------------------------------------------
            # Find function
            # -----------------------------------------------

            function = TOOL_FUNCTIONS.get(
                tool_name
            )


            if function is None:

                result = {

                    "success": False,

                    "error":
                        f"Unknown tool: {tool_name}"
                }

            else:

                try:

                    arguments = json.loads(
                        tool_call.function.arguments
                    )

                except json.JSONDecodeError:

                    arguments = {}


                # -------------------------------------------
                # REMEDIATION PROTECTION
                # -------------------------------------------

                if tool_name == "terminate_process":

                    result = {

                        "success": False,

                        "error":
                            """
                            Remediation requires explicit
                            user approval.

                            The agent cannot automatically
                            terminate processes.
                            """
                    }

                else:

                    # ---------------------------------------
                    # OBSERVATION TOOL
                    # ---------------------------------------

                    try:

                        result = function(
                            **arguments
                        )

                    except Exception as e:

                        result = {

                            "success": False,

                            "error":
                                str(e)
                        }


            # =================================================
            # SEND TOOL RESULT BACK TO MODEL
            # =================================================

            messages.append({

                "role":
                    "tool",

                "tool_call_id":
                    tool_call.id,

                "content":
                    json.dumps(
                        result,
                        default=str
                    )
            })
