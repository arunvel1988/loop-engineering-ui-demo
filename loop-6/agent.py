import json
import asyncio

from groq import Groq
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
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

# The FastMCP server is running on Uvicorn port 8000.
MCP_SERVER_URL = "http://127.0.0.1:8000/mcp"


def _mcp_tool_to_openai(tool):
    """
    Convert an MCP tool definition into the OpenAI/Groq function
    tool format expected by GPT-OSS.
    """
    input_schema = getattr(tool, "inputSchema", None)

    if input_schema is None:
        input_schema = {
            "type": "object",
            "properties": {},
            "required": []
        }

    # MCP uses inputSchema; OpenAI/Groq function tools use parameters.
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": input_schema
        }
    }


def _mcp_result_to_dict(result):
    """
    Convert an MCP CallToolResult into JSON-safe data for GPT-OSS.
    """
    output = {
        "success": not bool(getattr(result, "isError", False)),
    }

    structured = getattr(result, "structuredContent", None)
    if structured:
        output["data"] = structured

    content_items = getattr(result, "content", None) or []
    texts = []

    for item in content_items:
        text_value = getattr(item, "text", None)
        if text_value is not None:
            texts.append(text_value)
        else:
            # Keep non-text MCP content visible without assuming a
            # particular SDK content class.
            try:
                texts.append(str(item))
            except Exception:
                pass

    if texts:
        output["output"] = "\n".join(texts)

    if getattr(result, "isError", False):
        output["error"] = output.get("output", "MCP tool returned an error.")

    return output


async def _discover_mcp_tools_async():
    """
    Discover MCP tools.

    IMPORTANT:
    The entire Streamable HTTP client lifecycle is contained in
    this coroutine. Nothing from the MCP context is returned or
    reused after this coroutine exits.
    """
    async with streamablehttp_client(MCP_SERVER_URL) as (
        read_stream,
        write_stream,
        _,
    ):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.list_tools()

            tools = [
                _mcp_tool_to_openai(tool)
                for tool in result.tools
            ]

            print(f"[MCP] Discovered {len(tools)} tools.")
            return tools


async def _call_mcp_tool_async(session, tool_name, arguments):
    """
    Call an MCP tool using the SAME ClientSession that was created
    for the current agent execution.

    This function must only be called while that session's async
    context is still active.
    """
    result = await session.call_tool(
        tool_name,
        arguments=arguments or {}
    )
    return _mcp_result_to_dict(result)


async def _run_agent_mcp_loop(messages, pending_action):
    """
    Run the GPT-OSS tool loop and MCP session inside ONE asyncio
    event loop and ONE Streamable HTTP session.

    This is the critical fix for:
      - ClosedResourceError
      - GeneratorExit
      - cancel scope entered/exited in different task
    """

    async with streamablehttp_client(MCP_SERVER_URL) as (
        read_stream,
        write_stream,
        _,
    ):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            tool_result = await session.list_tools()

            tools = [
                _mcp_tool_to_openai(tool)
                for tool in tool_result.tools
            ]

            print(f"[MCP] Discovered {len(tools)} tools.")

            while True:
                # Groq's Python SDK is synchronous. Calling it here is
                # safe for this single-request Flask architecture; the
                # important part is that MCP remains inside this one
                # async lifecycle.
                response = client.chat.completions.create(
                    model=MODEL,
                    messages=messages,
                    tools=tools,
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
                    return (
                        message.content or "",
                        pending_action
                    )

                # Add the assistant message containing the tool calls.
                messages.append(message)

                # ----------------------------------------------------
                # PROCESS TOOL CALLS
                # ----------------------------------------------------
                for tool_call in message.tool_calls:

                    tool_name = tool_call.function.name

                    try:
                        arguments = json.loads(
                            tool_call.function.arguments or "{}"
                        )
                    except (json.JSONDecodeError, TypeError):
                        arguments = {}

                    # =================================================
                    # DESTRUCTIVE REMEDIATION
                    # =================================================
                    #
                    # terminate_process is exposed by MCP, but the
                    # agent intercepts it BEFORE sending it to MCP.
                    # The actual destructive operation only happens
                    # after explicit human approval in app.py.
                    #
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
                                        "error": (
                                            "PID 1 cannot be terminated."
                                        )
                                    }
                                else:
                                    pending_action = {
                                        "tool": "terminate_process",
                                        "arguments": {
                                            "pid": pid
                                        },
                                        "description": (
                                            f"Terminate process PID {pid}"
                                        )
                                    }

                                    result = {
                                        "success": False,
                                        "requires_approval": True,
                                        "pid": pid,
                                        "message": (
                                            f"Termination of PID {pid} "
                                            "requires human approval."
                                        )
                                    }

                    # =================================================
                    # MCP READ/SAFE TOOLS
                    # =================================================
                    else:
                        try:
                            result = await _call_mcp_tool_async(
                                session,
                                tool_name,
                                arguments
                            )

                        except Exception as e:
                            print(
                                f"[MCP] Tool call failed: "
                                f"{tool_name}: {e}"
                            )

                            result = {
                                "success": False,
                                "error": (
                                    f"MCP tool '{tool_name}' failed: "
                                    f"{str(e)}"
                                )
                            }

                    # Send MCP/tool result back to GPT-OSS.
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


def _run_async(coro):
    """
    Run one complete async operation.

    Flask is synchronous in this application, so each call gets its
    own event loop. MCP resources NEVER escape that event loop.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    # This branch is only relevant if run_agent is unexpectedly called
    # from an already-running event loop. Run the coroutine in a
    # dedicated thread so asyncio.run() still owns the complete
    # lifecycle.
    import threading

    result = {}
    error = {}

    def runner():
        try:
            result["value"] = asyncio.run(coro)
        except BaseException as exc:
            error["value"] = exc

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    thread.join()

    if "value" in error:
        raise error["value"]

    return result.get("value")


def discover_mcp_tools():
    """
    Public synchronous helper used for diagnostics/tests.
    """
    try:
        return _run_async(
            _discover_mcp_tools_async()
        )
    except Exception as e:
        print(f"[MCP] Tool discovery failed: {e}")
        return []


def call_mcp_tool(tool_name, arguments=None):
    """
    Public synchronous helper for app.py approval/verification code.

    It creates one complete MCP lifecycle for this single operation.
    It does NOT retain an async session between Flask requests.
    """
    async def call_once():
        async with streamablehttp_client(MCP_SERVER_URL) as (
            read_stream,
            write_stream,
            _,
        ):
            async with ClientSession(
                read_stream,
                write_stream
            ) as session:
                await session.initialize()

                return await _call_mcp_tool_async(
                    session,
                    tool_name,
                    arguments or {}
                )

    try:
        return _run_async(call_once())
    except Exception as e:
        print(
            f"[MCP] Tool call failed: {tool_name}: {e}"
        )

        return {
            "success": False,
            "error": str(e)
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

Current infrastructure:

- check_server
- check_processes
- check_ports
- check_docker

Historical operational memory:

- search_previous_incidents

Remediation:

- terminate_process


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
    - MCP infrastructure tools
    - human-approved remediation

    MCP lifecycle design:

        run_agent()
            |
            +-- asyncio.run()
                  |
                  +-- connect MCP
                  +-- initialize session
                  +-- discover tools
                  +-- GPT tool loop
                  +-- close session
            |
            +-- save long-term memory

    No MCP async object is retained across Flask requests or event
    loops.
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

    long_term_memories = get_long_term_memory(task)

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

    rag_results = get_rag_knowledge(task)

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

            role = item.get("role")
            content = item.get("content", "")

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
    # COMPLETE MCP + GPT TOOL LOOP
    # ========================================================

    try:
        final_response, pending_action = _run_async(
            _run_agent_mcp_loop(
                messages,
                pending_action
            )
        )

    except Exception as e:

        print(
            f"[AGENT] MCP/agent execution failed: {e}"
        )

        final_response = (
            "I could not complete the infrastructure "
            "investigation because the MCP server connection "
            f"failed: {str(e)}"
        )

    # ========================================================
    # SAVE LONG-TERM MEMORY
    # ========================================================

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


