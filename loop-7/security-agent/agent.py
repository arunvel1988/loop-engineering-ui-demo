import json
import os
import subprocess
import uuid
from typing import Any

from groq import Groq

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import (
    create_agent_card_routes,
    create_jsonrpc_routes,
)
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater

from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentSkill,
    Part,
    TaskState,
)

from a2a.helpers import new_text_message

from starlette.applications import Starlette
import uvicorn


# ============================================================
# CONFIGURATION
# ============================================================

HOST = os.getenv("A2A_HOST", "0.0.0.0")
PORT = int(os.getenv("A2A_PORT", "9000"))

PUBLIC_URL = os.getenv(
    "A2A_PUBLIC_URL",
    f"http://localhost:{PORT}",
)

MODEL = os.getenv(
    "GROQ_MODEL",
    "openai/gpt-oss-120b",
)


# ============================================================
# GROQ CLIENT
# ============================================================

client = Groq()


# ============================================================
# HELPER
# ============================================================

def run_command(
    command: str,
    timeout: int = 20,
) -> str:
    """
    Execute a read-only Linux command.

    Security note:
    This Security Agent intentionally only exposes
    predefined commands. User input is NOT passed
    directly into a shell command.
    """

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        stdout = result.stdout.strip()
        stderr = result.stderr.strip()

        if stdout:
            return stdout

        if stderr:
            return f"Command error:\n{stderr}"

        return "No output returned."

    except subprocess.TimeoutExpired:
        return "Command timed out."

    except Exception as exc:
        return f"Command execution failed: {exc}"


# ============================================================
# SECURITY TOOLS
# ============================================================

def check_open_ports() -> str:
    """
    Check listening TCP/UDP ports and associated processes.
    """

    return run_command(
        "ss -tulnp"
    )


def check_processes() -> str:
    """
    Show the processes consuming the most CPU.
    """

    return run_command(
        "ps aux --sort=-%cpu | head -20"
    )


def check_logged_in_users() -> str:
    """
    Show currently logged-in users.
    """

    return run_command(
        "who"
    )


def check_failed_logins() -> str:
    """
    Look for failed authentication attempts.
    """

    command = (
        "journalctl --no-pager -n 500 2>/dev/null "
        "| grep -Ei "
        "'failed password|authentication failure|invalid user|"
        "failed login|failure' "
        "| tail -50"
    )

    result = run_command(command)

    if result and "No output returned" not in result:
        return result

    # Fallback for systems where journalctl does not contain
    # authentication information.
    return run_command(
        "lastb -n 30 2>/dev/null"
    )


def check_world_writable_files() -> str:
    """
    Find world-writable files in selected directories.

    We intentionally limit the search to avoid scanning
    the entire filesystem.
    """

    return run_command(
        "find /tmp /var/tmp /opt "
        "-xdev -type f -perm -0002 "
        "-printf '%p\\n' "
        "2>/dev/null | head -100"
    )


def check_suid_files() -> str:
    """
    Find SUID binaries in common system directories.
    """

    return run_command(
        "find /usr/bin /usr/sbin /bin /sbin "
        "-xdev -type f -perm -4000 "
        "-printf '%p\\n' "
        "2>/dev/null | head -200"
    )


def check_security_services() -> str:
    """
    Inspect security-related services.
    """

    return run_command(
        "systemctl --no-pager --type=service --state=running "
        "2>/dev/null "
        "| grep -Ei "
        "'ssh|sshd|fail2ban|ufw|audit|firewalld'"
    )


def check_system_info() -> str:
    """
    Collect basic host information.
    """

    hostname = run_command(
        "hostname"
    )

    os_info = run_command(
        "cat /etc/os-release 2>/dev/null "
        "| grep -E '^(NAME|VERSION)='"
    )

    kernel = run_command(
        "uname -a"
    )

    uptime = run_command(
        "uptime"
    )

    return (
        "HOSTNAME:\n"
        f"{hostname}\n\n"
        "OS:\n"
        f"{os_info}\n\n"
        "KERNEL:\n"
        f"{kernel}\n\n"
        "UPTIME:\n"
        f"{uptime}"
    )


def security_audit() -> str:
    """
    Run the complete read-only security audit.
    """

    results = {}

    print("\n[SECURITY TOOL] Running complete security audit...")

    print("[SECURITY TOOL] Checking system information...")
    results["system_info"] = check_system_info()

    print("[SECURITY TOOL] Checking open ports...")
    results["open_ports"] = check_open_ports()

    print("[SECURITY TOOL] Checking processes...")
    results["processes"] = check_processes()

    print("[SECURITY TOOL] Checking logged-in users...")
    results["logged_in_users"] = check_logged_in_users()

    print("[SECURITY TOOL] Checking failed logins...")
    results["failed_logins"] = check_failed_logins()

    print("[SECURITY TOOL] Checking world-writable files...")
    results["world_writable_files"] = check_world_writable_files()

    print("[SECURITY TOOL] Checking SUID files...")
    results["suid_files"] = check_suid_files()

    print("[SECURITY TOOL] Checking security services...")
    results["security_services"] = check_security_services()

    return json.dumps(
        results,
        indent=2,
    )


# ============================================================
# TOOL REGISTRY
# ============================================================

TOOL_FUNCTIONS = {
    "check_open_ports": check_open_ports,
    "check_processes": check_processes,
    "check_logged_in_users": check_logged_in_users,
    "check_failed_logins": check_failed_logins,
    "check_world_writable_files": check_world_writable_files,
    "check_suid_files": check_suid_files,
    "check_security_services": check_security_services,
    "check_system_info": check_system_info,
    "security_audit": security_audit,
}


# ============================================================
# GROQ TOOL DEFINITIONS
# ============================================================

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "check_open_ports",
            "description": (
                "Check listening TCP and UDP ports and "
                "the processes associated with them."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_processes",
            "description": (
                "Check currently running Linux processes, "
                "especially high CPU processes."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_logged_in_users",
            "description": (
                "Check users currently logged into the Linux server."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_failed_logins",
            "description": (
                "Check failed authentication and login attempts."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_world_writable_files",
            "description": (
                "Find world-writable files in selected "
                "Linux directories."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_suid_files",
            "description": (
                "Find SUID files in common Linux system directories."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_security_services",
            "description": (
                "Check running security-related services "
                "such as SSH, fail2ban, UFW, auditd and firewalld."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_system_info",
            "description": (
                "Collect hostname, operating system, kernel "
                "and uptime information."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "security_audit",
            "description": (
                "Run a complete read-only Linux security audit "
                "including ports, processes, authentication, "
                "SUID files, world-writable files, security "
                "services and system information."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
]


# ============================================================
# SECURITY AGENT SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """
You are a defensive Linux Security Investigation Agent.

Your job is to investigate security questions using REAL
telemetry from the Linux server.

You are a READ-ONLY security agent.

============================================================
CORE RULES
============================================================

1. NEVER invent security findings.

2. NEVER invent:
   - ports
   - processes
   - PIDs
   - usernames
   - login attempts
   - files
   - services
   - vulnerabilities
   - IP addresses
   - commands
   - evidence

3. Use security tools whenever current telemetry is required.

4. A listening port is NOT automatically a vulnerability.

5. A running process is NOT automatically malicious.

6. A failed login attempt is NOT automatically evidence
   of a successful compromise.

7. A world-writable file is NOT automatically malicious.

8. A SUID binary is NOT automatically malicious.

9. Distinguish between:
   - Observation
   - Evidence
   - Risk
   - Hypothesis
   - Confirmed finding

10. If evidence is insufficient, explicitly say:

    "Insufficient evidence to determine this."

============================================================
SECURITY SEVERITY
============================================================

Use severity only when supported by evidence.

Possible levels:

LOW
MEDIUM
HIGH
CRITICAL

Do not assign HIGH or CRITICAL simply because something
looks unusual.

============================================================
READ-ONLY POLICY
============================================================

You MUST NOT perform destructive actions.

Never:

- kill processes
- delete files
- modify files
- modify permissions
- modify firewall rules
- disable services
- create users
- delete users
- change passwords
- install packages
- modify SSH configuration
- modify system configuration

You can recommend remediation steps, but you must not
execute them.

============================================================
INVESTIGATION WORKFLOW
============================================================

Follow this workflow:

1. UNDERSTAND THE SECURITY QUESTION

2. COLLECT CURRENT TELEMETRY

3. CORRELATE THE EVIDENCE

4. IDENTIFY POSSIBLE SECURITY RISKS

5. DISTINGUISH FACT FROM HYPOTHESIS

6. DETERMINE WHETHER THERE IS SUFFICIENT EVIDENCE

7. RECOMMEND SAFE REMEDIATION

============================================================
RESPONSE FORMAT
============================================================

Return:

Security Investigation
----------------------

Overall Assessment:
<summary>

Findings:
1. <finding>
2. <finding>

Evidence:
- <actual evidence>

Risk:
<LOW / MEDIUM / HIGH / CRITICAL>

Recommended Remediation:
- <recommendation>

Action Required:
<what the infrastructure/security team should investigate
or change>

============================================================
A2A ROLE
============================================================

You are a specialist Security Agent.

Another agent may delegate security investigations to you
through the A2A protocol.

When receiving an A2A request:

- investigate the requested security issue
- use real telemetry
- produce a concise security report
- return the result to the calling agent
- do not perform destructive remediation
"""


# ============================================================
# GROQ AGENT
# ============================================================

def run_agent(user_input: str) -> str:

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": user_input,
        },
    ]

    print("\n" + "=" * 60)
    print("SECURITY AGENT")
    print("=" * 60)

    print(f"Request: {user_input}")
    print(f"Model: {MODEL}")

    max_iterations = 12

    for iteration in range(max_iterations):

        print(
            f"\n[AGENT LOOP] Iteration {iteration + 1}"
        )

        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            temperature=0.2,
            max_completion_tokens=4096,
            reasoning_effort="medium",
        )

        message = response.choices[0].message

        # ----------------------------------------------------
        # No tool calls -> final response
        # ----------------------------------------------------

        if not message.tool_calls:

            final_response = message.content or ""

            print("\n[AGENT] Final response generated.")

            return final_response

        # ----------------------------------------------------
        # Add assistant tool-call message
        # ----------------------------------------------------

        assistant_message = {
            "role": "assistant",
            "content": message.content or "",
            "tool_calls": [],
        }

        for tool_call in message.tool_calls:

            assistant_message["tool_calls"].append(
                {
                    "id": tool_call.id,
                    "type": "function",
                    "function": {
                        "name": tool_call.function.name,
                        "arguments": tool_call.function.arguments,
                    },
                }
            )

        messages.append(assistant_message)

        # ----------------------------------------------------
        # Execute tools
        # ----------------------------------------------------

        for tool_call in message.tool_calls:

            function_name = tool_call.function.name
            arguments = tool_call.function.arguments

            print(
                f"\n[TOOL CALL] {function_name}"
            )

            print(
                f"[TOOL ARGS] {arguments}"
            )

            function = TOOL_FUNCTIONS.get(function_name)

            if function is None:

                result = (
                    f"Unknown security tool: "
                    f"{function_name}"
                )

            else:

                try:

                    parsed_arguments = {}

                    if arguments:
                        parsed_arguments = json.loads(
                            arguments
                        )

                    result = function(
                        **parsed_arguments
                    )

                except Exception as exc:

                    result = (
                        f"Security tool failed: {exc}"
                    )

            print(
                f"[TOOL RESULT] {function_name}"
            )

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": str(result),
                }
            )

    return (
        "The security investigation exceeded the maximum "
        "number of investigation steps."
    )


# ============================================================
# A2A EXECUTOR
# ============================================================

class SecurityAgentExecutor(AgentExecutor):
    """
    Connects the Groq Security Agent to the A2A protocol.
    """

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:

        # ----------------------------------------------------
        # Get or create task
        # ----------------------------------------------------

        task = context.current_task

        if task is None:

            # The current A2A SDK expects the request task
            # to be created and placed on the event queue.
            from a2a.helpers import new_task_from_user_message

            task = new_task_from_user_message(
                context.message
            )

            await event_queue.enqueue_event(task)

        # ----------------------------------------------------
        # Create TaskUpdater
        # ----------------------------------------------------

        updater = TaskUpdater(
            event_queue=event_queue,
            task_id=task.id,
            context_id=task.context_id,
        )

        # ----------------------------------------------------
        # TASK -> WORKING
        # ----------------------------------------------------

        await updater.update_status(
            state=TaskState.TASK_STATE_WORKING
        )

        try:

            # ------------------------------------------------
            # Get incoming A2A message
            # ------------------------------------------------

            user_input = context.get_user_input()

            print("\n")
            print("=" * 60)
            print("INCOMING A2A SECURITY REQUEST")
            print("=" * 60)
            print(user_input)
            print("=" * 60)

            # ------------------------------------------------
            # Run Groq Security Agent
            # ------------------------------------------------

            response = run_agent(
                user_input
            )

            # ------------------------------------------------
            # Add result artifact
            # ------------------------------------------------

            await updater.add_artifact(
                parts=[
                    Part(
                        text=response
                    )
                ],
                name="security-investigation-result",
            )

            # ------------------------------------------------
            # TASK -> COMPLETED
            # ------------------------------------------------

            await updater.update_status(
                state=TaskState.TASK_STATE_COMPLETED
            )

            print("\n")
            print("=" * 60)
            print("A2A TASK COMPLETED")
            print("=" * 60)

        except Exception as exc:

            print("\n")
            print("=" * 60)
            print("A2A SECURITY AGENT ERROR")
            print("=" * 60)
            print(str(exc))
            print("=" * 60)

            # ------------------------------------------------
            # TASK -> FAILED
            # ------------------------------------------------

            await updater.update_status(
                state=TaskState.TASK_STATE_FAILED,
                message=new_text_message(
                    f"Security investigation failed: {exc}"
                ),
            )

    async def cancel(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:

        raise NotImplementedError(
            "Security Agent cancellation is not supported."
        )


# ============================================================
# AGENT SKILLS
# ============================================================

security_audit_skill = AgentSkill(
    id="security-audit",
    name="Security Audit",
    description=(
        "Perform a read-only security audit "
        "of a Linux server."
    ),
    tags=[
        "security",
        "audit",
        "linux",
        "server",
    ],
    examples=[
        "Perform a security audit",
        "Check this server for security issues",
        "Investigate suspicious activity",
    ],
)


authentication_skill = AgentSkill(
    id="authentication-analysis",
    name="Authentication Analysis",
    description=(
        "Analyze failed login and "
        "authentication activity."
    ),
    tags=[
        "authentication",
        "ssh",
        "login",
        "security",
    ],
    examples=[
        "Check failed SSH logins",
        "Look for suspicious authentication attempts",
    ],
)


network_skill = AgentSkill(
    id="network-analysis",
    name="Network Analysis",
    description=(
        "Inspect listening network ports "
        "and analyze exposed services."
    ),
    tags=[
        "network",
        "ports",
        "security",
    ],
    examples=[
        "Check open ports",
        "Analyze network exposure",
    ],
)


# ============================================================
# AGENT CARD
# ============================================================

agent_card = AgentCard(
    name="Security Agent",

    description=(
        "A defensive security investigation agent "
        "that performs read-only analysis of Linux servers."
    ),

    supported_interfaces=[
        AgentInterface(
            url=PUBLIC_URL,
            protocol_binding="JSONRPC",
            protocol_version="1.0",
        )
    ],

    capabilities=AgentCapabilities(
        streaming=False,
        push_notifications=False,
    ),

    default_input_modes=[
        "text/plain"
    ],

    default_output_modes=[
        "text/plain"
    ],

    skills=[
        security_audit_skill,
        authentication_skill,
        network_skill,
    ],
)


# ============================================================
# CREATE A2A SERVER
# ============================================================

def create_a2a_server():

    # --------------------------------------------------------
    # Task storage
    # --------------------------------------------------------

    task_store = InMemoryTaskStore()

    # --------------------------------------------------------
    # Agent executor
    # --------------------------------------------------------

    agent_executor = SecurityAgentExecutor()

    # --------------------------------------------------------
    # A2A request handler
    # --------------------------------------------------------

    request_handler = DefaultRequestHandler(
        agent_executor=agent_executor,
        task_store=task_store,
        agent_card=agent_card,
    )

    # --------------------------------------------------------
    # Routes
    # --------------------------------------------------------

    routes = []

    routes.extend(
        create_agent_card_routes(
            agent_card
        )
    )

    routes.extend(
        create_jsonrpc_routes(
            request_handler,
            "/",
        )
    )

    # --------------------------------------------------------
    # Starlette application
    # --------------------------------------------------------

    return Starlette(
        routes=routes
    )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    print()
    print("=" * 40)
    print("        SECURITY A2A AGENT")
    print("=" * 40)
    print()

    print(
        f"Server: http://localhost:{PORT}"
    )

    print()

    print(
        "Agent Card:"
    )

    print(
        f"{PUBLIC_URL}/.well-known/agent-card.json"
    )

    print()

    print(
        "A2A JSON-RPC endpoint:"
    )

    print(
        PUBLIC_URL
    )

    print()

    print(
        "A2A Protocol: 1.0"
    )

    print(
        f"Groq Model: {MODEL}"
    )

    print()

    print(
        "Security Mode: READ-ONLY"
    )

    print()

    print(
        "Starting server..."
    )

    print()

    app = create_a2a_server()

    uvicorn.run(
        app,
        host=HOST,
        port=PORT,
    )
