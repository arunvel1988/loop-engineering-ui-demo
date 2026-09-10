import json

from groq import Groq

from tools import TOOL_FUNCTIONS
from memory import save_memory, search_memory
from rag import search_knowledge


# ============================================================
# GROQ CONFIGURATION
# ============================================================

client = Groq()

MODEL = "openai/gpt-oss-120b"


# ============================================================
# MEMORY CONFIGURATION
# ============================================================

# Keep short-term conversation context small.
#
# Important because the current Groq tier has an 8000 TPM
# limitation for GPT-OSS 120B.
MAX_SHORT_TERM_MESSAGES = 8

# Maximum long-term memories retrieved from ChromaDB.
MAX_LONG_TERM_MEMORIES = 3

# Maximum durable memories created from one interaction.
MAX_NEW_MEMORIES = 3

# Maximum RAG knowledge chunks retrieved for one request.
MAX_RAG_RESULTS = 2

# Keep retrieved knowledge compact to protect Groq TPM.
MAX_RAG_CHUNK_CHARS = 1800


# ============================================================
# MCP CONFIGURATION
# ============================================================

MCP_SERVER_URL = "http://localhost:8080/mcp"
MCP_TOOLS = []

import asyncio
import threading

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


def _run_async(coro):
    """Run an async MCP operation from the synchronous Flask app."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    result = {}
    error = {}

    def runner():
        try:
            result["value"] = asyncio.run(coro)
        except Exception as exc:
            error["value"] = exc

    thread = threading.Thread(target=runner)
    thread.start()
    thread.join()

    if "value" in error:
        raise error["value"]

    return result.get("value")


async def _discover_mcp_tools():
    """Connect to MCP and convert discovered tools to Groq tool format."""
    async with streamablehttp_client(MCP_SERVER_URL) as (
        read_stream,
        write_stream,
        _,
    ):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            response = await session.list_tools()

            tools = []

            for tool in response.tools:
                schema = getattr(tool, "inputSchema", None)

                if schema is None:
                    schema = {
                        "type": "object",
                        "properties": {},
                        "required": [],
                    }

                tools.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": (
                            tool.description
                            or f"MCP tool: {tool.name}"
                        ),
                        "parameters": schema,
                    },
                })

            return tools


async def _call_mcp_tool(tool_name, arguments):
    """Call one tool on the external MCP server."""
    async with streamablehttp_client(MCP_SERVER_URL) as (
        read_stream,
        write_stream,
        _,
    ):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            result = await session.call_tool(
                tool_name,
                arguments=arguments,
            )

            output = []

            for content in result.content:
                if hasattr(content, "text"):
                    output.append(content.text)
                elif hasattr(content, "model_dump"):
                    output.append(content.model_dump())
                else:
                    output.append(str(content))

            if len(output) == 1:
                try:
                    return json.loads(output[0])
                except (json.JSONDecodeError, TypeError):
                    return output[0]

            return output


def get_mcp_tools():
    """Discover tools exposed by mcp_server.py."""
    global MCP_TOOLS

    try:
        MCP_TOOLS = _run_async(_discover_mcp_tools())

        print(
            f"[MCP] Discovered {len(MCP_TOOLS)} tools."
        )

        return MCP_TOOLS

    except Exception as e:
        print(
            f"[MCP] Tool discovery failed: {e}"
        )
        return []


def call_mcp_tool(tool_name, arguments):
    """Synchronous wrapper for MCP tool execution."""
    return _run_async(
        _call_mcp_tool(
            tool_name,
            arguments,
        )
    )


# ============================================================
# LOCAL HISTORICAL INCIDENT TOOL
# ============================================================

INCIDENT_DB_PATH = "devops_agent.db"


def search_previous_incidents(
    alertname=None,
    severity=None,
    limit=5,
):
    """Search historical incidents in the local SQLite database."""

    try:
        limit = max(1, min(int(limit or 5), 10))

        import sqlite3

        conn = sqlite3.connect(INCIDENT_DB_PATH)
        conn.row_factory = sqlite3.Row

        query = """
            SELECT
                id,
                alertname,
                severity,
                status,
                summary,
                description,
                agent_response,
                remediation_status,
                remediation_result,
                verification,
                created_at
            FROM incidents
            WHERE 1=1
        """

        params = []

        if alertname:
            query += " AND alertname = ?"
            params.append(alertname)

        if severity:
            query += " AND severity = ?"
            params.append(severity)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        conn.close()

        results = []

        for row in rows:
            item = dict(row)

            if item.get("agent_response"):
                if len(item["agent_response"]) > 1000:
                    item["agent_response"] = (
                        item["agent_response"][:1000] + "..."
                    )

            results.append(item)

        return results

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


HISTORY_TOOL = {
    "type": "function",
    "function": {
        "name": "search_previous_incidents",
        "description": (
            "Search previous DevOps incidents stored in the "
            "incident database. Use this during incident "
            "investigation to find similar past incidents, "
            "root causes and remediation results. Historical "
            "incidents are supporting evidence only."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "alertname": {
                    "type": "string",
                    "description": "Alert name such as HighCPU.",
                },
                "severity": {
                    "type": "string",
                    "description": "Severity such as critical or warning.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of incidents.",
                },
            },
            "required": [],
        },
    },
}


# ============================================================
# SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """
You are a professional DevOps incident investigation agent.

Your job is to investigate infrastructure problems using
REAL information collected from tools.

You must behave like a production SRE.


===========================================================
1. CONVERSATION MEMORY
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

When the user asks about CURRENT infrastructure state,
always use the appropriate infrastructure tool.


===========================================================
2. LONG-TERM CONVERSATIONAL MEMORY
===========================================================

You may receive relevant long-term memories retrieved
from ChromaDB.

These memories represent durable information learned
from previous conversations.

Examples:

- application names
- project information
- architecture information
- infrastructure conventions
- persistent configuration
- stable user preferences
- recurring operational preferences

Use long-term memories when they are relevant.

IMPORTANT:

Long-term conversational memory is NOT live infrastructure
telemetry.

For example, if memory says:

"The user's application is called ecommerce-app."

that should be used when the user asks:

"What is my application called?"

However, if the user asks:

"What containers are currently running?"

you MUST use the Docker tool.

Do not confuse an application name with:

- Docker Compose project name
- container name
- service name
- hostname
- infrastructure resource name

These can be different things.


===========================================================
3. MEMORY QUESTIONS VS CURRENT STATE QUESTIONS
===========================================================

This distinction is VERY IMPORTANT.

If the user asks about something previously told to the
agent, use long-term memory.

Examples:

"What is my application called?"

"What application do I use?"

"What database did I tell you I use?"

"What architecture did I tell you about?"

"What are my DevOps preferences?"

"What container name did I tell you earlier?"

For these questions, do NOT automatically call infrastructure
tools.

Use the relevant long-term memory.

However, if the user asks about CURRENT infrastructure:

"What containers are running now?"

"What is the CPU right now?"

"What ports are open now?"

"Is Docker running now?"

"What is the current memory usage?"

then call the appropriate live infrastructure tool.

NEVER replace a memory answer with unrelated live telemetry.

For example:

If long-term memory says:

"The user's application is called ecommerce-app."

and Docker reports:

"Compose project = monitoring"

then:

"What is my application called?"

must be answered:

"ecommerce-app"

It must NOT be answered:

"monitoring"

because monitoring is the Docker Compose project name,
not necessarily the application name.


===========================================================
4. RAG / DEVOPS KNOWLEDGE
===========================================================

You may receive relevant knowledge retrieved from the DevOps
knowledge base. The knowledge base contains PDF documentation
about Docker, Linux and DevOps troubleshooting.

Use this knowledge as GENERAL OPERATIONAL GUIDANCE.

IMPORTANT:

RAG knowledge is documentation. It is NOT live infrastructure
telemetry.

For example, if the retrieved knowledge says:

"Use ps aux --sort=-%cpu to find CPU-intensive processes."

and the user asks:

"Which process is using the most CPU right now?"

you MUST call check_processes because the actual answer requires
current server information.

If the user asks:

"How do I investigate high CPU on Linux?"

use the retrieved Linux knowledge to explain the procedure.

When RAG knowledge and current tool output are both available:

- Use RAG for procedures, concepts and troubleshooting guidance.
- Use live tools for current infrastructure facts.
- Never invent live values from documentation.
- Never treat documentation as proof of the current root cause.
- If live telemetry conflicts with documentation, trust the live
  telemetry for the current incident.

The retrieved knowledge may also help you decide which
infrastructure tool should be called next.


===========================================================
5. CURRENT TELEMETRY
===========================================================

Use current infrastructure tools to collect real data.

Never invent:

- CPU values
- memory values
- disk values
- process names
- process IDs
- ports
- Docker containers
- service states
- infrastructure status


If the user asks:

"What is CPU now?"

call:

check_server

Do not answer using an old conversation value.

If the user asks:

"What processes are using CPU now?"

call:

check_processes

If the user asks:

"What containers are running now?"

call:

check_docker

If the user asks:

"What ports are listening now?"

call:

check_ports


===========================================================
6. INVESTIGATION WORKFLOW
===========================================================

For infrastructure incidents:

1. CHECK INCIDENT HISTORY WHEN RELEVANT
2. OBSERVE CURRENT INFRASTRUCTURE
3. INVESTIGATE
4. CORRELATE EVIDENCE
5. IDENTIFY ROOT CAUSE
6. RECOMMEND REMEDIATION
7. VERIFY


===========================================================
7. AVAILABLE TOOLS
===========================================================

Infrastructure tools are provided dynamically by the external
MCP server.

The MCP server can expose tools for:

- Linux/server inspection
- process inspection
- network ports
- Docker
- systemd services
- remediation actions

Historical operational memory:

- search_previous_incidents

The infrastructure tools are MCP tools. Use the tool descriptions
provided by the MCP server rather than assuming a fixed list.


===========================================================
8. CPU INCIDENT
===========================================================

If server CPU is significantly elevated and a process is
using approximately 100% CPU, investigate whether that
process correlates with the elevated CPU usage.

Only request termination when CURRENT evidence supports it.

Never use historical incidents as proof of the current
root cause.


===========================================================
9. HISTORICAL INCIDENT MEMORY
===========================================================

Previous incidents are historical operational evidence.

Use search_previous_incidents when relevant.

Historical incidents are supporting evidence only.

They must NEVER be treated as proof of the current root cause.

If historical evidence conflicts with current telemetry,
trust current telemetry.


===========================================================
10. ROOT CAUSE
===========================================================

Only identify a root cause when evidence supports it.

If evidence is insufficient, say:

"Root cause could not be conclusively identified from the
available telemetry."


===========================================================
11. REMEDIATION
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
12. LONG-TERM MEMORY SAFETY
===========================================================

Not every conversation message should become memory.

Only remember durable and useful information.

Good memories:

- application names
- project names
- architecture
- persistent configuration
- infrastructure conventions
- stable preferences
- recurring operational preferences

Do NOT remember:

- greetings
- temporary CPU values
- temporary memory values
- temporary disk values
- temporary process IDs
- one-time investigation results
- casual conversation
- passwords
- API keys
- secrets
- access tokens


===========================================================
13. RESPONSE FORMAT
===========================================================

For infrastructure investigations use:

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
    Search ChromaDB for memories relevant to the user's
    current request.
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
# BUILD MEMORY CONTEXT
# ============================================================

def build_memory_context(memories):
    """
    Convert ChromaDB search results into a compact
    context block for GPT-OSS.
    """

    if not memories:
        return ""

    lines = [
        "===========================================================",
        "RELEVANT LONG-TERM MEMORY",
        "===========================================================",
        "",
        "These are memories retrieved from previous conversations.",
        "Use them only when relevant to the user's question.",
        "",
    ]

    for index, item in enumerate(
        memories,
        start=1
    ):

        memory = item.get(
            "memory",
            ""
        )

        if not memory:
            continue

        # Keep memory small to protect Groq TPM.
        if len(memory) > 1000:
            memory = (
                memory[:1000]
                + "..."
            )

        lines.append(
            f"{index}. {memory}"
        )

    lines.append("")

    return "\n".join(lines)


# ============================================================
# EXTRACT DURABLE MEMORIES
# ============================================================

def extract_memories(
    task,
    response
):
    """
    Ask GPT-OSS to identify durable information worth
    storing in ChromaDB.

    This is NOT a tool call.
    """

    if not response:
        return []

    memory_prompt = f"""
You are a long-term memory extraction system.

Read the interaction below and identify only information
that is likely to remain useful in future conversations.

Good examples:

- application names
- project names
- architecture
- infrastructure configuration
- persistent preferences
- stable DevOps conventions
- recurring operational preferences

Do NOT save:

- greetings
- temporary CPU values
- temporary memory values
- temporary disk values
- temporary process IDs
- one-time incident results
- temporary infrastructure state
- casual conversation
- passwords
- API keys
- secrets
- access tokens

IMPORTANT:

Do not reinterpret or invent information.

Only extract facts explicitly supported by the interaction.

Return ONLY valid JSON.

Exact format:

{{
  "memories": [
    "memory 1",
    "memory 2"
  ]
}}

If nothing is worth remembering:

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
                        "You extract durable long-term "
                        "memories. Return only JSON."
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

        content = (
            result
            .choices[0]
            .message
            .content
            or ""
        )

        content = content.strip()


        # ----------------------------------------------------
        # Parse normal JSON
        # ----------------------------------------------------

        try:

            data = json.loads(
                content
            )

        except json.JSONDecodeError:

            # ------------------------------------------------
            # Handle markdown JSON
            # ------------------------------------------------

            if content.startswith(
                "```"
            ):

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

                data = json.loads(
                    content
                )

            except json.JSONDecodeError:

                print(
                    "[MEMORY] Could not parse memory JSON."
                )

                return []


        memories = data.get(
            "memories",
            []
        )

        if not isinstance(
            memories,
            list
        ):
            return []


        cleaned = []

        for memory in memories:

            if not isinstance(
                memory,
                str
            ):
                continue

            memory = memory.strip()

            if not memory:
                continue

            if len(memory) > 1000:

                memory = memory[:1000]


            cleaned.append(
                memory
            )

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
    Extract durable memories from the interaction and
    store them in ChromaDB.
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
                conversation_id=(
                    conversation_id
                    or "unknown"
                ),
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
# RAG KNOWLEDGE SEARCH
# ============================================================

def get_rag_knowledge(task):
    """
    Search the DevOps knowledge base for documentation relevant
    to the current request.

    This retrieves knowledge from the PDF documents ingested into
    ChromaDB by rag_ingest.py.

    RAG provides documentation and troubleshooting guidance.
    It does NOT provide live infrastructure state.
    """

    try:

        results = search_knowledge(
            query=task,
            limit=MAX_RAG_RESULTS
        )

        if not results:
            return []

        return results

    except Exception as e:

        print(
            f"[RAG] Knowledge search failed: {e}"
        )

        return []


# ============================================================
# BUILD RAG CONTEXT
# ============================================================

def build_rag_context(results):
    """
    Convert retrieved ChromaDB results into a compact context
    block for GPT-OSS.
    """

    if not results:
        return ""

    lines = [
        "===========================================================",
        "RELEVANT DEVOPS KNOWLEDGE (RAG)",
        "===========================================================",
        "",
        "The following information was retrieved from the DevOps",
        "knowledge base PDFs.",
        "",
        "Use it as documentation and troubleshooting guidance.",
        "Do not treat it as live infrastructure telemetry.",
        "",
    ]

    for index, item in enumerate(
        results,
        start=1
    ):

        content = item.get(
            "content",
            ""
        )

        if not content:
            continue

        if len(content) > MAX_RAG_CHUNK_CHARS:
            content = (
                content[:MAX_RAG_CHUNK_CHARS]
                + "..."
            )

        source = item.get(
            "source",
            "unknown"
        )

        page = item.get(
            "page",
            "unknown"
        )

        distance = item.get(
            "distance"
        )

        if isinstance(distance, (int, float)):
            distance_text = f"{distance:.4f}"
        else:
            distance_text = "unknown"

        lines.append(
            f"SOURCE {index}: {source}, page {page}, "
            f"distance {distance_text}"
        )
        lines.append("")
        lines.append(content)
        lines.append("")

    return "\\n".join(lines)


# ============================================================
# MAIN AGENT
# ============================================================

def run_agent(
    task,
    conversation_history=None,
    conversation_id=None
):
    """
    Run GPT-OSS 120B with:

    - short-term conversation memory
    - long-term ChromaDB memory
    - RAG knowledge from PDF documents
    - MCP-provided DevOps tools
    - human-approved remediation
    """

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        }
    ]


    # ========================================================
    # LONG-TERM MEMORY
    # ========================================================

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


    # ========================================================
    # RAG KNOWLEDGE
    # ========================================================

    rag_results = get_rag_knowledge(
        task
    )

    rag_context = build_rag_context(
        rag_results
    )

    if rag_context:

        messages.append(
            {
                "role": "system",
                "content": rag_context
            }
        )


    # ========================================================
    # SHORT-TERM MEMORY
    # ========================================================

    if conversation_history:

        recent_history = conversation_history[
            -MAX_SHORT_TERM_MESSAGES:
        ]

        for item in recent_history:

            role = item.get(
                "role"
            )

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

            # Protect Groq TPM.
            if len(content) > 3000:

                content = (
                    content[:3000]
                    + "..."
                )

            messages.append(
                {
                    "role": role,
                    "content": content
                }
            )


    # ========================================================
    # CURRENT REQUEST
    # ========================================================

    messages.append(
        {
            "role": "user",
            "content": task
        }
    )


    pending_action = None


    # ========================================================
    # DISCOVER MCP TOOLS
    # ========================================================

    mcp_tools = get_mcp_tools()

    # Historical incident search remains local because it uses
    # the agent application's SQLite operational-memory database.
    available_tools = mcp_tools + [HISTORY_TOOL]


    # ========================================================
    # AGENT TOOL LOOP
    # ========================================================

    while True:

        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=available_tools,
            tool_choice="auto",
            temperature=0.2,
            max_completion_tokens=2048,
            reasoning_effort="medium"
        )


        message = response.choices[0].message


        # ====================================================
        # NO TOOL CALL
        # ====================================================

        if not message.tool_calls:

            final_response = (
                message.content
                or ""
            )


            # =================================================
            # SAVE LONG-TERM MEMORY
            # =================================================

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


        # ====================================================
        # ADD ASSISTANT TOOL CALL
        # ====================================================

        messages.append(
            message
        )


        # ====================================================
        # PROCESS TOOL CALLS
        # ====================================================

        for tool_call in message.tool_calls:

            tool_name = (
                tool_call
                .function
                .name
            )


            # ------------------------------------------------
            # Parse tool arguments
            # ------------------------------------------------

            try:

                arguments = json.loads(
                    tool_call
                    .function
                    .arguments
                )

            except json.JSONDecodeError:

                arguments = {}


            # =================================================
            # DESTRUCTIVE REMEDIATION
            # =================================================

            if tool_name == "terminate_process":

                pid = arguments.get("pid")

                if pid is None:
                    result = {
                        "success": False,
                        "requires_approval": False,
                        "error": "No PID was provided.",
                    }

                else:

                    try:
                        pid = int(pid)
                    except (ValueError, TypeError):

                        result = {
                            "success": False,
                            "requires_approval": False,
                            "error": "Invalid PID.",
                        }

                    else:

                        if pid == 1:

                            result = {
                                "success": False,
                                "requires_approval": False,
                                "error": "PID 1 cannot be terminated.",
                            }

                        else:

                            pending_action = {
                                "tool": "terminate_process",
                                "arguments": {
                                    "pid": pid
                                },
                                "description": (
                                    f"Terminate process PID {pid}"
                                ),
                            }

                            result = {
                                "success": False,
                                "requires_approval": True,
                                "pid": pid,
                                "message": (
                                    f"Termination of PID {pid} "
                                    "requires human approval."
                                ),
                            }


            # =================================================
            # HISTORICAL INCIDENT SEARCH
            # =================================================

            elif tool_name == "search_previous_incidents":

                try:
                    result = search_previous_incidents(**arguments)

                except Exception as e:
                    result = {
                        "success": False,
                        "error": str(e),
                    }


            # =================================================
            # MCP TOOL
            # =================================================

            else:

                mcp_tool_names = {
                    item["function"]["name"]
                    for item in mcp_tools
                }

                if tool_name not in mcp_tool_names:

                    result = {
                        "success": False,
                        "error": (
                            f"Unknown MCP tool: {tool_name}"
                        ),
                    }

                else:

                    try:

                        result = call_mcp_tool(
                            tool_name,
                            arguments,
                        )

                    except Exception as e:

                        result = {
                            "success": False,
                            "error": (
                                f"MCP tool '{tool_name}' "
                                f"failed: {e}"
                            ),
                        }


            # =================================================
            # SEND TOOL RESULT BACK TO GPT
            # =================================================

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
