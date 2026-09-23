import json
import os
import subprocess

import uvicorn
from groq import Groq

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater

from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentSkill,
    Part,
    TextPart,
)

from a2a.server.apps import A2AStarletteApplication


# =========================================================
# CONFIGURATION
# =========================================================

HOST = os.getenv(
    "A2A_HOST",
    "0.0.0.0"
)

PORT = int(
    os.getenv(
        "A2A_PORT",
        "9000"
    )
)

PUBLIC_URL = os.getenv(
    "A2A_PUBLIC_URL",
    f"http://localhost:{PORT}"
)


# =========================================================
# GROQ CLIENT
# =========================================================

client = Groq()

MODEL = os.getenv(
    "GROQ_MODEL",
    "openai/gpt-oss-120b"
)


# =========================================================
# COMMAND EXECUTION
# =========================================================

def run_command(command):
    """
    Execute a read-only Linux security command.

    IMPORTANT:
    This Security Agent is intentionally read-only.
    """

    try:

        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=15,
        )

        return {
            "success": result.returncode == 0,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "return_code": result.returncode,
        }

    except subprocess.TimeoutExpired:

        return {
            "success": False,
            "error": "Command timed out."
        }

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }


# =========================================================
# SECURITY TOOL IMPLEMENTATIONS
# =========================================================

def check_open_ports():

    return run_command(
        "ss -tulnp"
    )


def check_processes():

    return run_command(
        "ps aux --sort=-%cpu | head -20"
    )


def check_logged_in_users():

    return run_command(
        "who"
    )


def check_failed_logins():

    command = (
        "journalctl --no-pager -n 200 2>/dev/null "
        "| grep -Ei "
        "'failed|invalid|authentication failure' "
        "| tail -30"
    )

    result = run_command(command)

    if result.get("stdout"):

        return result

    return run_command(
        "lastb -n 30 2>/dev/null"
    )


def check_world_writable_files():

    command = (
        "find /tmp /var/tmp /opt "
        "-xdev -type f -perm -0002 "
        "-print 2>/dev/null "
        "| head -50"
    )

    return run_command(command)


def check_suid_files():

    command = (
        "find /usr/bin /usr/sbin /bin /sbin "
        "-xdev -type f -perm -4000 "
        "-print 2>/dev/null "
        "| head -50"
    )

    return run_command(command)


def check_security_services():

    command = (
        "systemctl --no-pager "
        "--type=service "
        "--state=running "
        "2>/dev/null "
        "| grep -Ei "
        "'ssh|fail2ban|ufw|audit|firewalld'"
    )

    return run_command(command)


def check_system_info():

    command = (
        "echo '=== HOSTNAME ==='; "
        "hostname; "
        "echo '=== OS ==='; "
        "cat /etc/os-release 2>/dev/null | head -8; "
        "echo '=== KERNEL ==='; "
        "uname -a; "
        "echo '=== UPTIME ==='; "
        "uptime"
    )

    return run_command(command)


def security_audit():

    return {

        "system_info":
            check_system_info(),

        "open_ports":
            check_open_ports(),

        "processes":
            check_processes(),

        "logged_in_users":
            check_logged_in_users(),

        "failed_logins":
            check_failed_logins(),

        "world_writable_files":
            check_world_writable_files(),

        "suid_files":
            check_suid_files(),

        "security_services":
            check_security_services(),
    }


# =========================================================
# TOOL REGISTRY
# =========================================================

TOOL_FUNCTIONS = {

    "check_open_ports":
        check_open_ports,

    "check_processes":
        check_processes,

    "check_logged_in_users":
        check_logged_in_users,

    "check_failed_logins":
        check_failed_logins,

    "check_world_writable_files":
        check_world_writable_files,

    "check_suid_files":
        check_suid_files,

    "check_security_services":
        check_security_services,

    "check_system_info":
        check_system_info,

    "security_audit":
        security_audit,
}


# =========================================================
# GROQ TOOL DEFINITIONS
# =========================================================

TOOLS = [

    {
        "type": "function",

        "function": {

            "name":
                "check_open_ports",

            "description":
                "Check TCP and UDP ports currently "
                "listening on the server.",

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
                "List running processes sorted by CPU "
                "usage. Use this to identify unusual "
                "or potentially suspicious processes.",

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
                "check_logged_in_users",

            "description":
                "Check users currently logged into "
                "the server.",

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
                "check_failed_logins",

            "description":
                "Check recent failed SSH and "
                "authentication attempts.",

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
                "check_world_writable_files",

            "description":
                "Find world-writable files in selected "
                "system directories.",

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
                "check_suid_files",

            "description":
                "Find SUID executables in common "
                "system directories.",

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
                "check_security_services",

            "description":
                "Check common security-related services "
                "such as SSH, UFW, Fail2ban and audit "
                "services.",

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
                "check_system_info",

            "description":
                "Collect hostname, operating system, "
                "kernel and uptime information.",

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
                "security_audit",

            "description":
                "Perform a comprehensive read-only "
                "security audit of the server.",

            "parameters": {

                "type": "object",

                "properties": {},

                "required": []
            }
        }
    }

]


# =========================================================
# SECURITY AGENT SYSTEM PROMPT
# =========================================================

SYSTEM_PROMPT = """

You are a professional Security Operations Agent.

You are a defensive security specialist.

Your job is to investigate Linux server security
issues using REAL information collected from tools.

You may receive requests directly from a user or
from another AI agent through the A2A protocol.

===========================================================
PRIMARY RESPONSIBILITY
===========================================================

You are responsible for security investigation.

The DevOps Agent is responsible for broader
infrastructure operations.

When another agent delegates a security investigation
to you, perform the security analysis and return
your findings to the requesting agent.

===========================================================
INVESTIGATION WORKFLOW
===========================================================

Follow this workflow:

1. Understand the security question.

2. Collect current system information.

3. Inspect network exposure.

4. Inspect running processes.

5. Inspect authentication activity.

6. Check filesystem permissions.

7. Check security services.

8. Correlate the evidence.

9. Identify potential security risks.

10. Recommend remediation.

11. Report the findings.

===========================================================
AVAILABLE TOOLS
===========================================================

Network:

- check_open_ports

Processes:

- check_processes

Authentication:

- check_logged_in_users
- check_failed_logins

Filesystem:

- check_world_writable_files
- check_suid_files

Security services:

- check_security_services

System:

- check_system_info

Complete audit:

- security_audit

===========================================================
REAL DATA RULE
===========================================================

Always use REAL information returned by tools.

Never invent:

- IP addresses
- ports
- processes
- PIDs
- usernames
- login attempts
- services
- files
- vulnerabilities
- security findings

If information is unavailable, say so.

===========================================================
NETWORK SECURITY RULE
===========================================================

A listening port is NOT automatically a vulnerability.

For example:

0.0.0.0:22

does not automatically mean the server
has been compromised.

Determine:

- what is listening
- which process owns the port
- whether the service is expected
- whether additional evidence indicates risk

===========================================================
PROCESS SECURITY RULE
===========================================================

A process is NOT automatically malicious because:

- it is unfamiliar
- it is written in Python
- it runs as root
- it uses CPU
- it listens on a port

Additional evidence is required.

===========================================================
AUTHENTICATION RULE
===========================================================

Failed authentication attempts can represent:

- accidental login failures
- incorrect passwords
- automated scanning
- brute-force attempts

Do not automatically claim compromise.

Look for:

- frequency
- source information
- usernames
- timing
- repeated patterns
- supporting evidence

===========================================================
FILESYSTEM RULE
===========================================================

World-writable and SUID files may require investigation.

Do not automatically classify them as malicious.

Consider:

- file location
- owner
- permissions
- expected system behavior
- supporting evidence

===========================================================
SEVERITY
===========================================================

When evidence supports a finding, classify it as:

CRITICAL
HIGH
MEDIUM
LOW
INFORMATIONAL

Do not assign a high severity without evidence.

===========================================================
READ-ONLY SECURITY AGENT
===========================================================

This agent is currently READ-ONLY.

NEVER:

- kill processes
- delete files
- modify permissions
- disable users
- block IP addresses
- change firewall rules
- restart services
- modify configuration
- install software

Instead, provide recommended remediation.

Actual remediation can be implemented later
through an explicit approval workflow.

===========================================================
A2A ROLE
===========================================================

You are a specialist Security Agent.

Another agent may send you a task through A2A.

For example:

"Investigate whether this server has
potential security issues."

When receiving an A2A task:

1. Understand the requested investigation.

2. Collect real evidence.

3. Analyze the evidence.

4. Identify supported findings.

5. Explain uncertainty.

6. Return a concise security report.

Do not perform destructive remediation.

===========================================================
RESPONSE FORMAT
===========================================================

Return:

Security Investigation

Overall Assessment

Findings

Evidence

Risk

Recommended Remediation

Action Required

Keep the response concise and evidence-based.

"""


# =========================================================
# RUN SECURITY AGENT
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


    while True:

        response = client.chat.completions.create(

            model=MODEL,

            messages=messages,

            tools=TOOLS,

            tool_choice="auto",

            temperature=0.2,

            max_completion_tokens=2048,

            reasoning_effort="medium",
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
                    message.content or ""
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
            # PARSE ARGUMENTS
            # -------------------------------------------------

            try:

                arguments = json.loads(
                    tool_call
                    .function
                    .arguments
                )

            except json.JSONDecodeError:

                arguments = {}


            # -------------------------------------------------
            # FIND TOOL
            # -------------------------------------------------

            function = TOOL_FUNCTIONS.get(
                tool_name
            )


            if not function:

                result = {

                    "success":
                        False,

                    "error":
                        f"Unknown security tool: "
                        f"{tool_name}"
                }

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
            # SEND TOOL RESULT BACK TO GROQ
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


# =========================================================
# A2A EXECUTOR
# =========================================================

class SecurityAgentExecutor(
    AgentExecutor
):

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:

        # -------------------------------------------------
        # Get incoming A2A task
        # -------------------------------------------------

        user_input = (
            context.get_user_input()
        )

        print()
        print("========================================")
        print("A2A REQUEST RECEIVED")
        print("========================================")
        print(user_input)
        print()

        # -------------------------------------------------
        # Run Security Agent
        # -------------------------------------------------

        result = run_agent(
            user_input
        )

        response = result.get(
            "response",
            "Security investigation completed."
        )

        # -------------------------------------------------
        # Task updater
        # -------------------------------------------------

        updater = TaskUpdater(
            event_queue,
            context.task_id,
            context.context_id,
        )

        # -------------------------------------------------
        # Mark task as working
        # -------------------------------------------------

        await updater.update_status(
            "working"
        )

        # -------------------------------------------------
        # Return result as artifact
        # -------------------------------------------------

        await updater.add_artifact(

            [
                Part(
                    root=TextPart(
                        text=response
                    )
                )
            ],

            name="security-investigation-result",
        )

        # -------------------------------------------------
        # Complete task
        # -------------------------------------------------

        await updater.complete()


    async def cancel(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:

        print(
            "A2A task cancellation requested."
        )


# =========================================================
# AGENT CARD
# =========================================================

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


agent_card = AgentCard(

    name="Security Agent",

    description=(
        "A defensive security investigation agent "
        "that performs read-only analysis of "
        "Linux servers."
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
        "text"
    ],

    default_output_modes=[
        "text"
    ],

    skills=[

        security_audit_skill,

        authentication_skill,

        network_skill,
    ],
)


# =========================================================
# CREATE A2A SERVER
# =========================================================

def create_a2a_server():

    # -----------------------------------------------------
    # Task storage
    # -----------------------------------------------------

    task_store = (
        InMemoryTaskStore()
    )


    # -----------------------------------------------------
    # Agent executor
    # -----------------------------------------------------

    agent_executor = (
        SecurityAgentExecutor()
    )


    # -----------------------------------------------------
    # Request handler
    # -----------------------------------------------------

    request_handler = (
        DefaultRequestHandler(

            agent_executor=
                agent_executor,

            task_store=
                task_store,

            agent_card=
                agent_card,
        )
    )


    # -----------------------------------------------------
    # A2A Starlette application
    # -----------------------------------------------------

    server = (
        A2AStarletteApplication(

            agent_card=
                agent_card,

            http_handler=
                request_handler,
        )
    )


    return server.build()


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    print()
    print("========================================")
    print("        SECURITY A2A AGENT")
    print("========================================")
    print()

    print(
        f"Server : {PUBLIC_URL}"
    )

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
        "Starting server..."
    )

    print()

    app = create_a2a_server()

    uvicorn.run(

        app,

        host=HOST,

        port=PORT,
    )
