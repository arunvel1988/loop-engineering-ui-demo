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

            "name":
                "search_previous_incidents",

            "description":
                "Search previous DevOps incidents stored "
                "in the incident database. Use this during "
                "incident investigation to look for similar "
                "past incidents, previous root causes and "
                "previous remediation results. Historical "
                "incidents are supporting evidence only and "
                "must never be treated as proof of the "
                "current root cause.",

            "parameters": {

                "type": "object",

                "properties": {

                    "alertname": {

                        "type": "string",

                        "description":
                            "Alert name to search for, "
                            "such as HighCPU."

                    },

                    "severity": {

                        "type": "string",

                        "description":
                            "Optional severity such as "
                            "critical or warning."

                    },

                    "limit": {

                        "type": "integer",

                        "description":
                            "Maximum number of previous "
                            "incidents to return. Keep "
                            "this small, normally 3 to 5."

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

            "name":
                "terminate_process",

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

1. CHECK INCIDENT HISTORY
2. OBSERVE CURRENT INFRASTRUCTURE
3. INVESTIGATE
4. CORRELATE PAST AND CURRENT EVIDENCE
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
INCIDENT HISTORY
===========================================================

When investigating an automatically generated incident,
use search_previous_incidents when relevant.

For example, if the current alert is:

HighCPU

search:

search_previous_incidents(
    alertname="HighCPU",
    limit=5
)

Historical incidents can reveal:

- recurring problems
- previous root causes
- previous processes involved
- previous remediation actions
- patterns across incidents

IMPORTANT:

Historical evidence is NOT proof of the current root cause.

You MUST inspect current infrastructure telemetry.

===========================================================
CURRENT TELEMETRY
===========================================================

Use the current infrastructure tools to collect real data.

For infrastructure incidents, use tools such as:

check_server
check_processes
check_ports
check_docker

Do not invent infrastructure information.

Never invent:

- CPU values
- memory values
- disk values
- process names
- process IDs
- ports
- Docker containers
- service states

===========================================================
CORRELATION
===========================================================

Compare historical evidence with current telemetry.

Example:

Historical:

Previous HighCPU incidents involved
the "yes" process.

Current:

yes PID 20001 is consuming 98% CPU.

Correlation:

The historical pattern matches the current
CPU telemetry.

This can strengthen the root-cause conclusion.

However:

Historical evidence alone is never enough.

===========================================================
ROOT CAUSE RULES
===========================================================

Only identify a root cause when evidence supports it.

Do NOT assume that something is the root cause simply
because it exists.

A process listening on a port is NOT automatically
a performance problem.

A Python process is NOT automatically a problem.

A Flask process is NOT automatically a problem.

A user-space process is NOT automatically a problem.

A low-CPU process is NOT automatically a problem.

A listening port is NOT evidence of a bottleneck by itself.

===========================================================
CPU INCIDENT
===========================================================

If server CPU is significantly elevated and a process is
using approximately 100% CPU, investigate whether that
process correlates with the elevated CPU usage.

Example:

Server CPU = 50%

Process:

yes

PID = 15992

CPU = approximately 100%

This is strong evidence that the process may be responsible
for the CPU-related incident.

If current evidence supports this conclusion, you may
request termination of that exact PID.

===========================================================
HEALTHY SERVER
===========================================================

If telemetry shows:

CPU = 1%
Memory = 10%
Disk = 5%

and there is no high-CPU process:

DO NOT invent a root cause.

Report:

"No clear infrastructure bottleneck was detected."

Additional application-level telemetry may be required.

===========================================================
NETWORK PORT RULE
===========================================================

Do NOT identify a process as the root cause merely because
it is listening on a network port.

Example:

0.0.0.0:5000
PID 17958

does NOT prove that PID 17958 is causing slowness.

Additional evidence is required.

===========================================================
DOCKER RULE
===========================================================

If Docker is relevant, inspect Docker state.

Look for:

- unhealthy containers
- repeatedly restarting containers
- failed containers
- obvious resource problems

Do not claim a Docker problem without evidence.

===========================================================
REMEDIATION RULE
===========================================================

terminate_process is a destructive remediation action.

NEVER execute destructive remediation automatically.

When strong current evidence shows that a specific process
is causing the incident:

Call:

terminate_process(pid)

The application intercepts the tool call.

The application does NOT immediately terminate the process.

Instead it creates a human approval request.

The human must click:

"Approve & Execute"

before the operation happens.

===========================================================
TERMINATION SAFETY
===========================================================

Never request termination of:

PID 1

Never invent a PID.

Never terminate a process merely because:

- it owns a port
- it is Python
- it is Flask
- it is a user process
- it has low CPU
- it appeared in an old incident

The PID MUST come from CURRENT telemetry.

===========================================================
IMPORTANT
===========================================================

If historical incidents suggest one cause but current
telemetry suggests another cause, trust current telemetry.

If historical incidents exist but the current telemetry
does not support the historical pattern, do not claim
the historical cause is responsible.

If evidence is insufficient, say:

"Root cause could not be conclusively identified from the
available telemetry."

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

Keep the response concise and evidence-based.

===========================================================
REMEDIATION REQUEST
===========================================================

When strong evidence supports terminating a process:

1. Explain the evidence.
2. Identify the exact PID from CURRENT telemetry.
3. Call terminate_process with that PID.
4. Wait for the application to request human approval.

Do NOT merely write:

"Please approve termination."

You MUST call the terminate_process tool when remediation
is justified.

The application will turn the tool call into an approval
button.

"""


# =========================================================
# RUN AGENT
# =========================================================

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

            # Reduced from 4096
            max_completion_tokens=2048,

            reasoning_effort="medium"

        )


        message = (
            response
            .choices[0]
            .message
        )


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
                tool_call
                .function
                .name
            )


            # -------------------------------------------------
            # Parse arguments
            # -------------------------------------------------

            try:

                arguments = json.loads(
                    tool_call
                    .function
                    .arguments
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

                        "success":
                            False,

                        "requires_approval":
                            False,

                        "error":
                            "No PID was provided."

                    }


                else:

                    try:

                        pid = int(pid)


                    except (
                        ValueError,
                        TypeError
                    ):

                        result = {

                            "success":
                                False,

                            "requires_approval":
                                False,

                            "error":
                                "Invalid PID."

                        }

                    else:

                        # -----------------------------------------
                        # Never allow PID 1
                        # -----------------------------------------

                        if pid == 1:

                            result = {

                                "success":
                                    False,

                                "requires_approval":
                                    False,

                                "error":
                                    "PID 1 cannot be terminated."

                            }

                        else:

                            # -------------------------------------
                            # CREATE PENDING APPROVAL
                            # -------------------------------------

                            pending_action = {

                                "tool":
                                    "terminate_process",

                                "arguments": {

                                    "pid":
                                        pid

                                },

                                "description":
                                    f"Terminate process PID {pid}"

                            }


                            # -------------------------------------
                            # DO NOT EXECUTE
                            # -------------------------------------

                            result = {

                                "success":
                                    False,

                                "requires_approval":
                                    True,

                                "pid":
                                    pid,

                                "message":
                                    f"Termination of PID {pid} "
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
