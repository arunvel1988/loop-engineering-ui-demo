import json

from groq import Groq

from tools import TOOL_FUNCTIONS


# =========================================================
# GROQ CLIENT
# =========================================================

client = Groq()

MODEL = "openai/gpt-oss-120b"


# =========================================================
# TOOL DEFINITIONS
# =========================================================

TOOLS = [

    # -----------------------------------------------------
    # SERVER HEALTH
    # -----------------------------------------------------

    {
        "type": "function",

        "function": {

            "name": "check_server",

            "description":
                "Check CPU, memory and disk usage "
                "of the server.",

            "parameters": {

                "type": "object",

                "properties": {},

                "required": []

            }

        }

    },


    # -----------------------------------------------------
    # PROCESSES
    # -----------------------------------------------------

    {
        "type": "function",

        "function": {

            "name": "check_processes",

            "description":
                "List the top processes sorted by "
                "CPU usage. Use this to identify "
                "runaway or CPU-intensive processes.",

            "parameters": {

                "type": "object",

                "properties": {},

                "required": []

            }

        }

    },


    # -----------------------------------------------------
    # NETWORK PORTS
    # -----------------------------------------------------

    {
        "type": "function",

        "function": {

            "name": "check_ports",

            "description":
                "Check listening network ports on "
                "the server.",

            "parameters": {

                "type": "object",

                "properties": {},

                "required": []

            }

        }

    },


    # -----------------------------------------------------
    # DOCKER
    # -----------------------------------------------------

    {
        "type": "function",

        "function": {

            "name": "check_docker",

            "description":
                "Check Docker containers and their "
                "current state.",

            "parameters": {

                "type": "object",

                "properties": {},

                "required": []

            }

        }

    },


    # -----------------------------------------------------
    # INCIDENT MEMORY
    # -----------------------------------------------------

    {
        "type": "function",

        "function": {

            "name": "search_previous_incidents",

            "description":
                "Search historical DevOps incidents stored "
                "in the incident database. Use this during "
                "incident investigation to determine whether "
                "similar incidents occurred previously. "
                "Historical incidents are supporting evidence "
                "only and must not be treated as proof of the "
                "current root cause.",

            "parameters": {

                "type": "object",

                "properties": {

                    "alertname": {

                        "type": "string",

                        "description":
                            "Optional alert name to search for, "
                            "for example HighCPU."

                    },

                    "severity": {

                        "type": "string",

                        "description":
                            "Optional severity to search for, "
                            "for example critical or warning."

                    },

                    "limit": {

                        "type": "integer",

                        "description":
                            "Maximum number of historical "
                            "incidents to return. Use a small "
                            "number such as 5."

                    }

                },

                "required": []

            }

        }

    },


    # -----------------------------------------------------
    # PROCESS TERMINATION
    # -----------------------------------------------------

    {
        "type": "function",

        "function": {

            "name": "terminate_process",

            "description":
                "Request termination of a specific "
                "process by PID when investigation "
                "shows that the process is causing "
                "the incident. This is a remediation "
                "proposal. The application intercepts "
                "this request and requires human approval "
                "before actually terminating the process.",

            "parameters": {

                "type": "object",

                "properties": {

                    "pid": {

                        "type": "integer",

                        "description":
                            "PID of the process that "
                            "should be terminated."

                    }

                },

                "required": [
                    "pid"
                ]

            }

        }

    }

]


# =========================================================
# SYSTEM PROMPT
# =========================================================

SYSTEM_PROMPT = """

You are a professional DevOps incident investigation agent.

Your job is to investigate infrastructure problems using
REAL information collected from tools.

You must behave like a production SRE.

===========================================================
INVESTIGATION WORKFLOW
===========================================================

Follow this workflow:

1. OBSERVE
2. CHECK INCIDENT HISTORY
3. INVESTIGATE
4. CORRELATE
5. IDENTIFY ROOT CAUSE
6. RECOMMEND REMEDIATION
7. VERIFY

===========================================================
AVAILABLE OBSERVATION TOOLS
===========================================================

You can use:

- check_server
- check_processes
- check_ports
- check_docker
- search_previous_incidents

Use the tools to collect real infrastructure data.

Never invent infrastructure information.

Never invent:

- CPU values
- memory values
- disk values
- process names
- process IDs
- ports
- Docker containers
- service states
- historical incidents

===========================================================
INCIDENT HISTORY
===========================================================

Historical incidents are available through:

search_previous_incidents

Use this tool when investigating an incident.

Historical incidents can help you determine:

- whether the same alert happened before
- whether similar symptoms occurred before
- whether the same process appeared in previous incidents
- whether previous remediation actions were successful
- whether there is a recurring pattern

IMPORTANT:

Historical incidents are supporting evidence.

They are NOT proof of the current root cause.

For example:

Previous incident:

HighCPU
Root cause:
yes process

This does NOT mean the current HighCPU incident
is automatically caused by yes.

You must inspect CURRENT telemetry.

For example:

Historical evidence:

yes caused HighCPU twice previously

Current evidence:

yes PID 20001 = 98% CPU

These two pieces of evidence can be correlated.

Only then can you consider the yes process a strong
candidate for the current root cause.

===========================================================
ROOT CAUSE RULES
===========================================================

Only identify a root cause when the evidence supports it.

Do NOT assume that something is the root cause simply
because it exists.

For example:

A process listening on port 5000 is NOT automatically
a performance problem.

A user-space process is NOT automatically a problem.

A low-CPU process is NOT automatically a problem.

A listening port is NOT evidence of a bottleneck by itself.

A Python process running Flask is NOT automatically the
cause of server slowness.

===========================================================
CPU INCIDENT
===========================================================

If server CPU is significantly elevated and a process is
using approximately 100% CPU, investigate whether that
process correlates with the elevated CPU usage.

For example:

Server CPU = 50%

Process:

yes

PID = 15992

CPU = approximately 100%

This is strong evidence that the process may be responsible
for the CPU-related incident.

In that situation you may request termination of that
specific PID.

===========================================================
HEALTHY SERVER
===========================================================

If the telemetry shows something like:

CPU = 1%
Memory = 10%
Disk = 5%

and there is no high-CPU process,

DO NOT invent a root cause.

Instead report:

"No clear infrastructure bottleneck was detected."

Explain that additional application-level telemetry may
be required.

===========================================================
NETWORK PORT RULE
===========================================================

Do NOT identify a process as the root cause merely because
it is listening on a network port.

For example:

0.0.0.0:5000
PID 17958

does NOT prove that PID 17958 is causing slowness.

Only identify it as a root cause if additional evidence
supports that conclusion.

===========================================================
DOCKER RULE
===========================================================

If Docker containers are running, investigate their state
when relevant.

Look for:

- unhealthy containers
- repeatedly restarting containers
- failed containers
- obvious resource problems

Do not claim a Docker problem if the data does not support it.

===========================================================
REMEDIATION RULE
===========================================================

terminate_process is a destructive remediation action.

NEVER execute destructive remediation automatically.

When strong evidence shows that a specific process is
causing the incident, call:

terminate_process(pid)

The application will intercept this request.

The application will NOT immediately execute the operation.

Instead, the application will create a pending approval
request for the human operator.

The human must click:

"Approve & Execute"

before the process is actually terminated.

===========================================================
TERMINATION SAFETY
===========================================================

Never request termination of:

PID 1

Never invent a PID.

Never request termination of a process merely because:

- it owns a port
- it is a Python process
- it is a Flask process
- it is a user-space process
- it has low CPU usage

Only request termination when there is strong evidence
that the process is responsible for the incident.

===========================================================
AFTER REMEDIATION
===========================================================

After the human approves the remediation, the application
will execute the action and collect new telemetry.

The verification data should be used to determine whether
the incident has actually improved.

For example:

Before remediation:

CPU = 50%
yes PID 15992 = 100% CPU

After remediation:

CPU = 1%
yes PID 15992 no longer exists

This indicates that the CPU incident was successfully
remediated.

===========================================================
IMPORTANT REASONING RULE
===========================================================

Do not force yourself to find a root cause.

It is completely acceptable to say:

"Root cause could not be conclusively identified from the
available telemetry."

That is better than making an unsupported claim.

You are an SRE, not a guessing engine.

===========================================================
RESPONSE FORMAT
===========================================================

When investigation is complete, structure your response as:

Investigation Summary

Root Cause

Evidence

Historical Evidence

Recommended Remediation

Risk Assessment

Action Required

When historical incidents were used, clearly distinguish
historical evidence from current evidence.

For example:

Historical Evidence:
Previous HighCPU incidents involved the yes process.

Current Evidence:
The current yes process is consuming 99% CPU.

Correlation:
The historical pattern matches the current telemetry.

Do not claim historical evidence as current telemetry.

===========================================================
REMEDIATION REQUEST
===========================================================

When strong evidence supports terminating a process:

1. Explain the evidence.
2. Identify the exact PID.
3. Call terminate_process with that PID.
4. Wait for the application to request human approval.

Do NOT merely write:

"Please approve termination."

You MUST call the terminate_process tool when remediation
is justified.

The application will turn that tool call into an approval
button.

"""


# =========================================================
# RUN AGENT
# =========================================================

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


    # -----------------------------------------------------
    # Pending remediation requested by the agent
    # -----------------------------------------------------

    pending_action = None


    # =====================================================
    # AGENT LOOP
    # =====================================================

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


        # =================================================
        # FINAL RESPONSE
        # =================================================

        if not message.tool_calls:

            return {

                "response":
                    message.content or "",

                "pending_action":
                    pending_action

            }


        # =================================================
        # ADD ASSISTANT TOOL-CALL MESSAGE
        # =================================================

        messages.append(
            message
        )


        # =================================================
        # PROCESS TOOL CALLS
        # =================================================

        for tool_call in message.tool_calls:

            tool_name = (
                tool_call.function.name
            )


            # -------------------------------------------------
            # Parse arguments
            # -------------------------------------------------

            try:

                arguments = json.loads(
                    tool_call.function.arguments
                )

            except json.JSONDecodeError:

                arguments = {}


            # =================================================
            # REMEDIATION TOOL
            # =================================================

            if tool_name == "terminate_process":

                pid = arguments.get(
                    "pid"
                )


                # -------------------------------------------------
                # Validate PID
                # -------------------------------------------------

                if pid is None:

                    result = {

                        "success": False,

                        "requires_approval": False,

                        "error":
                            "No PID was provided."

                    }


                elif int(pid) == 1:

                    result = {

                        "success": False,

                        "requires_approval": False,

                        "error":
                            "PID 1 cannot be terminated."

                    }


                else:

                    # -------------------------------------------------
                    # CREATE PENDING APPROVAL
                    # -------------------------------------------------

                    pending_action = {

                        "tool":
                            "terminate_process",

                        "arguments": {

                            "pid":
                                int(pid)

                        },

                        "description":
                            f"Terminate process PID {int(pid)}"

                    }


                    # -------------------------------------------------
                    # IMPORTANT:
                    #
                    # DO NOT EXECUTE THE FUNCTION HERE.
                    #
                    # The UI must ask the human for approval.
                    # -------------------------------------------------

                    result = {

                        "success":
                            False,

                        "requires_approval":
                            True,

                        "pid":
                            int(pid),

                        "message":
                            f"Termination of PID {int(pid)} "
                            f"requires human approval."

                    }


            # =================================================
            # OBSERVATION TOOLS
            # =================================================

            else:

                function = TOOL_FUNCTIONS.get(
                    tool_name
                )


                # -------------------------------------------------
                # Unknown tool
                # -------------------------------------------------

                if not function:

                    result = {

                        "success":
                            False,

                        "error":
                            f"Unknown tool: {tool_name}"

                    }


                # -------------------------------------------------
                # Execute observation tool
                # -------------------------------------------------

                else:

                    try:

                        result = function(
                            **arguments
                        )

                    except Exception as e:

                        result = {

                            "success":
                                False,

                            "error":
                                str(e)

                        }


            # =================================================
            # SEND TOOL RESULT BACK TO GPT-OSS
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
