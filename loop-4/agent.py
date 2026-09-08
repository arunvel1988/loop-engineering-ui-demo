import json
from groq import Groq

from tools import TOOL_FUNCTIONS
from memory import save_memory, search_memory


# ============================================================
# GROQ
# ============================================================

client = Groq()

MODEL = "openai/gpt-oss-120b"


# ============================================================
# MEMORY CONFIGURATION
# ============================================================

# Keep short-term context small.
# This is important because GPT-OSS 120B has an 8000 TPM limit
# on your current Groq tier.
MAX_SHORT_TERM_MESSAGES = 8

# Maximum long-term memories added to the prompt.
MAX_LONG_TERM_MEMORIES = 3

# Maximum number of memories GPT is allowed to create
# from one interaction.
MAX_NEW_MEMORIES = 3


# ============================================================
# TOOLS
# ============================================================

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


# ============================================================
# SYSTEM PROMPT
# ============================================================

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
LONG-TERM CONVERSATIONAL MEMORY
===========================================================

You may also receive long-term memories retrieved from
the memory database.

These memories represent information learned from previous
conversations.

Examples:

- application names
- infrastructure preferences
- architecture information
- user preferences
- project information
- persistent configuration information

Use long-term memories when they are relevant.

IMPORTANT:

Long-term memory is not current infrastructure telemetry.

If a memory says:

"The application uses Docker."

and the user asks:

"What containers are running right now?"

you MUST use the Docker tool.

Never treat long-term memory as live infrastructure state.

If current tool data conflicts with memory, trust the current
tool data.


===========================================================
MEMORY SAFETY
===========================================================

Do not assume every statement should become long-term memory.

Only durable and useful information should be remembered.

Good memories include:

- application names
- project architecture
- persistent configuration
- stable user preferences
- infrastructure conventions
- recurring operational preferences

Do NOT remember:

- greetings
- temporary CPU values
- temporary memory values
- temporary process IDs
- one-time investigation results
- casual conversation
- secrets
- passwords
- API keys
- access tokens


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

Previous incidents are long-term operational history.

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


# ============================================================
# LONG-TERM MEMORY SEARCH
# ============================================================

def get_long_term_memory(task):
    """
    Search ChromaDB for memories relevant to the current request.
    """

    try:
        memories = search_memory(
            query=task,
            limit=MAX_LONG_TERM_MEMORIES
        )

        if not memories:
            return []

        return memories

    except Exception as e:
        print(
            f"[MEMORY] Long-term memory search failed: {e}"
        )

        return []


# ============================================================
# FORMAT LONG-TERM MEMORY FOR GPT
# ============================================================

def build_memory_context(memories):
    """
    Convert ChromaDB results into a compact prompt section.
    """

    if not memories:
        return ""

    lines = [
        "===========================================================",
        "RELEVANT LONG-TERM MEMORY",
        "===========================================================",
        "",
        "The following memories were retrieved from previous",
        "conversations. Use them only when relevant.",
        ""
    ]

    for index, item in enumerate(memories, start=1):

        memory = item.get("memory", "")

        if not memory:
            continue

        # Protect token usage.
        if len(memory) > 1000:
            memory = memory[:1000] + "..."

        lines.append(
            f"{index}. {memory}"
        )

    lines.append("")

    return "\n".join(lines)


# ============================================================
# EXTRACT LONG-TERM MEMORIES
# ============================================================

def extract_memories(task, response):
    """
    Ask GPT-OSS to identify durable information worth storing.

    This is a separate small Groq call.

    It does NOT execute tools.
    """

    if not response:
        return []

    memory_prompt = f"""
You are a memory extraction system.

Identify only durable information from this interaction that
would be useful in a future conversation.

Store useful facts such as:

- application names
- project architecture
- persistent configuration
- stable preferences
- infrastructure conventions
- recurring operational preferences

Do NOT store:

- greetings
- temporary CPU values
- temporary memory values
- temporary process IDs
- one-time investigation results
- casual conversation
- passwords
- API keys
- secrets
- access tokens

Return ONLY valid JSON.

Use this exact format:

{{
  "memories": [
    "memory 1",
    "memory 2"
  ]
}}

If there is nothing worth remembering:

{{
  "memories": []
}}

USER MESSAGE:
{task}

AGENT RESPONSE:
{response}
"""

    try:

        result = client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You extract durable long-term memories. "
                        "Return only JSON."
                    )
                },
                {
                    "role": "user",
                    "content": memory_prompt
                }
            ],
            temperature=0,
            max_completion_tokens=300,
            reasoning_effort="low"
        )

        content = result.choices[0].message.content or ""

        # ----------------------------------------------------
        # Parse JSON
        # ----------------------------------------------------

        try:
            data = json.loads(content)

        except json.JSONDecodeError:

            # Sometimes models wrap JSON in markdown.
            content = content.strip()

            if content.startswith("```"):
                content = content.replace(
                    "```json",
                    ""
                )

                content = content.replace(
                    "```",
                    ""
                )

                content = content.strip()

            try:
                data = json.loads(content)

            except json.JSONDecodeError:
                print(
                    "[MEMORY] Could not parse memory JSON."
                )
                return []

        memories = data.get(
            "memories",
            []
        )

        if not isinstance(memories, list):
            return []

        cleaned = []

        for memory in memories:

            if not isinstance(memory, str):
                continue

            memory = memory.strip()

            if not memory:
                continue

            if len(memory) > 1000:
                memory = memory[:1000]

            cleaned.append(memory)

            if len(cleaned) >= MAX_NEW_MEMORIES:
                break

        return cleaned

    except Exception as e:

        print(
            f"[MEMORY] Memory extraction failed: {e}"
        )

        return []


# ============================================================
# SAVE LONG-TERM MEMORIES
# ============================================================

def store_long_term_memories(
    conversation_id,
    task,
    response
):
    """
    Extract and save durable memories to ChromaDB.
    """

    if not response:
        return

    memories = extract_memories(
        task,
        response
    )

    if not memories:
        return

    for memory in memories:

        try:

            save_memory(
                conversation_id=conversation_id or "unknown",
                memory=memory,
                memory_type="conversation"
            )

            print(
                f"[MEMORY] Saved: {memory}"
            )

        except Exception as e:

            print(
                f"[MEMORY] Failed to save memory: {e}"
            )


# ============================================================
# AGENT
# ============================================================

def run_agent(
    task,
    conversation_history=None,
    conversation_id=None
):

    """
    Run GPT-OSS with:

    - short-term conversation memory
    - long-term ChromaDB memory
    - DevOps tools
    - human-approved remediation
    """

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        }
    ]


    # --------------------------------------------------------
    # LONG-TERM MEMORY
    # --------------------------------------------------------

    long_term_memories = get_long_term_memory(
        task
    )

    memory_context = build_memory_context(
        long_term_memories
    )

    if memory_context:

        messages.append(
            {
                "role": "system",
                "content": memory_context
            }
        )


    # --------------------------------------------------------
    # SHORT-TERM MEMORY
    # --------------------------------------------------------

    if conversation_history:

        recent_history = conversation_history[
            -MAX_SHORT_TERM_MESSAGES:
        ]

        for item in recent_history:

            role = item.get("role")

            content = item.get(
                "content",
                ""
            )

            if role not in [
                "user",
                "assistant"
            ]:
                continue

            if not content:
                continue

            # Protect TPM by limiting individual memory entries.
            if len(content) > 3000:
                content = content[:3000] + "..."

            messages.append(
                {
                    "role": role,
                    "content": content
                }
            )


    # --------------------------------------------------------
    # CURRENT REQUEST
    # --------------------------------------------------------

    messages.append(
        {
            "role": "user",
            "content": task
        }
    )


    pending_action = None


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
            max_completion_tokens=2048,
            reasoning_effort="medium"
        )

        message = response.choices[0].message


        # ----------------------------------------------------
        # NO TOOL CALL
        # ----------------------------------------------------

        if not message.tool_calls:

            final_response = message.content or ""


            # ------------------------------------------------
            # SAVE LONG-TERM MEMORY
            # ------------------------------------------------

            try:

                store_long_term_memories(
                    conversation_id=conversation_id,
                    task=task,
                    response=final_response
                )

            except Exception as e:

                print(
                    f"[MEMORY] Error storing memory: {e}"
                )


            return {
                "response": final_response,
                "pending_action": pending_action
            }


        # ----------------------------------------------------
        # Add assistant tool-call message
        # ----------------------------------------------------

        messages.append(message)


        # ----------------------------------------------------
        # PROCESS TOOL CALLS
        # ----------------------------------------------------

        for tool_call in message.tool_calls:

            tool_name = tool_call.function.name


            # ------------------------------------------------
            # Parse arguments
            # ------------------------------------------------

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

                pid = arguments.get(
                    "pid"
                )


                if pid is None:

                    result = {
                        "success": False,
                        "requires_approval": False,
                        "error": "No PID was provided."
                    }

                else:

                    try:

                        pid = int(pid)

                    except (
                        ValueError,
                        TypeError
                    ):

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

                function = TOOL_FUNCTIONS.get(
                    tool_name
                )


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


            # ------------------------------------------------
            # Give tool result back to model
            # ------------------------------------------------

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(
                        result,
                        default=str
                    )
                }
            )
