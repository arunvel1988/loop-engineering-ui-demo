import json
import os
import subprocess

from groq import Groq


# =========================================================
# GROQ CLIENT
# =========================================================

client = Groq()

MODEL = os.getenv(
    "GROQ_MODEL",
    "openai/gpt-oss-120b"
)


# =========================================================
# SECURITY TOOLS
# =========================================================

def run_command(command):
    """
    Run a read-only local security command.
    """

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=15
        )

        return {
            "success": result.returncode == 0,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "return_code": result.returncode
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
# TOOL IMPLEMENTATIONS
# =========================================================

def check_open_ports():
    """
    Check listening TCP and UDP ports.
    """

    return run_command(
        "ss -tulnp"
    )


def check_processes():
    """
    List processes consuming the most CPU and memory.
    """

    return run_command(
        "ps aux --sort=-%cpu | head -20"
    )


def check_logged_in_users():
    """
    Check currently logged-in users.
    """

    return run_command(
        "who"
    )


def check_failed_logins():
    """
    Check recent failed authentication attempts.

    Uses journalctl when available and falls back
    to lastb.
    """

    command = (
        "journalctl --no-pager -n 100 "
        "-u ssh 2>/dev/null | "
        "grep -Ei "
        "'failed|invalid|authentication failure' "
        " | tail -30"
    )

    result = run_command(command)

    if result["stdout"]:
        return result

    return run_command(
        "lastb -n 30 2>/dev/null"
    )


def check_world_writable_files():
    """
    Look for world-writable files in common system locations.

    This is intentionally limited to avoid scanning the
    entire filesystem.
    """

    command = (
        "find /tmp /var/tmp /opt "
        "-xdev -type f -perm -0002 "
        "-print 2>/dev/null | head -50"
    )

    return run_command(command)


def check_suid_files():
    """
    Find SUID executables in common system locations.
    """

    command = (
        "find /usr/bin /usr/sbin /bin /sbin "
        "-xdev -type f -perm -4000 "
        "-print 2>/dev/null | head -50"
    )

    return run_command(command)


def check_security_services():
    """
    Check common security-related services.
    """

    command = (
        "systemctl --no-pager --type=service "
        "--state=running 2>/dev/null | "
        "grep -Ei "
        "'ssh|fail2ban|ufw|audit|firewalld'"
    )

    return run_command(command)


def check_system_info():
    """
    Collect basic system information useful for
    security investigation.
    """

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
    """
    Run a collection of read-only security checks.
    """

    return {
        "system_info": check_system_info(),
        "open_ports": check_open_ports(),
        "processes": check_processes(),
        "logged_in_users": check_logged_in_users(),
        "failed_logins": check_failed_logins(),
        "world_writable_files": check_world_writable_files(),
        "suid_files": check_suid_files(),
        "security_services": check_security_services()
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

            "name": "check_open_ports",

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

            "name": "check_processes",

            "description":
                "List running processes sorted by CPU "
                "usage. Use this to identify suspicious "
                "or unusual processes.",

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

            "name": "check_logged_in_users",

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

            "name": "check_failed_logins",

            "description":
                "Check recent failed SSH or authentication "
                "attempts.",

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

            "name": "check_world_writable_files",

            "description":
                "Find world-writable files in selected "
                "system directories. These may represent "
                "potential security risks.",

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

            "name": "check_suid_files",

            "description":
                "Find SUID executables in common system "
                "directories.",

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

            "name": "check_security_services",

            "description":
                "Check whether common security-related "
                "services such as SSH, UFW, Fail2ban "
                "and audit services are running.",

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

            "name": "check_system_info",

            "description":
                "Collect basic hostname, operating system, "
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

            "name": "security_audit",

            "description":
                "Perform a comprehensive read-only security "
                "audit of the server. Use this when the user "
                "requests a general security assessment.",

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

Your job is to investigate server security issues using
REAL information collected from security tools.

You are a defensive security agent.

You must behave like a security analyst.

===========================================================
INVESTIGATION WORKFLOW
===========================================================

Follow this workflow:

1. UNDERSTAND THE SECURITY QUESTION
2. COLLECT CURRENT SYSTEM INFORMATION
3. INSPECT NETWORK EXPOSURE
4. INSPECT PROCESSES
5. INSPECT AUTHENTICATION ACTIVITY
6. CHECK FILE PERMISSIONS
7. CORRELATE EVIDENCE
8. IDENTIFY POTENTIAL SECURITY RISKS
9. RECOMMEND REMEDIATION
10. REPORT FINDINGS

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
IMPORTANT SECURITY RULES
===========================================================

Use REAL information from tools.

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

If information is unavailable, explicitly say so.

===========================================================
OPEN PORT RULE
===========================================================

A listening port is NOT automatically a vulnerability.

For example:

0.0.0.0:22

does not automatically mean the server is compromised.

Determine:

- what is listening
- which process owns the port
- whether the service is expected
- whether additional evidence indicates risk

===========================================================
PROCESS RULE
===========================================================

A process is NOT automatically malicious because:

- it is unfamiliar
- it is written in Python
- it is running as root
- it uses CPU
- it listens on a port

Additional evidence is required.

===========================================================
AUTHENTICATION RULE
===========================================================

Failed login attempts can indicate:

- accidental authentication failures
- password mistakes
- automated scanning
- brute-force attempts

Do not automatically claim compromise.

Look for patterns and supporting evidence.

===========================================================
FILE PERMISSION RULE
===========================================================

World-writable or SUID files may require investigation.

Do not automatically classify every such file as malicious.

Consider:

- file location
- ownership
- permissions
- expected system behavior
- additional evidence

===========================================================
SECURITY FINDING RULE
===========================================================

Separate findings into:

CRITICAL

HIGH

MEDIUM

LOW

INFORMATIONAL

Only assign severity when supported by evidence.

===========================================================
NO DESTRUCTIVE ACTION
===========================================================

This agent is currently READ-ONLY.

DO NOT:

- kill processes
- delete files
- modify permissions
- disable accounts
- block IP addresses
- modify firewall rules
- restart services
- modify system configuration

Instead, provide a recommended remediation.

Actual remediation can be implemented later
through an explicit approval workflow.

===========================================================
RESPONSE FORMAT
===========================================================

When the investigation is complete, structure the response as:

Security Investigation

Overall Assessment

Findings

Evidence

Risk

Recommended Remediation

Action Required

Keep the response concise and evidence-based.

===========================================================
A2A ROLE
===========================================================

You are a specialist Security Agent.

You may receive investigation tasks from another agent
through the A2A protocol.

The requesting agent may be a DevOps Agent.

When receiving an A2A task:

1. Understand the requested security investigation.
2. Collect real evidence using your tools.
3. Analyze the evidence.
4. Return a structured security finding.
5. Do not perform destructive remediation.

You are the security specialist.

The DevOps Agent is responsible for orchestrating
the broader infrastructure investigation.
"""


# =========================================================
# RUN SECURITY AGENT
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


        # =================================================
        # FINAL RESPONSE
        # =================================================

        if not message.tool_calls:

            return {
                "response": message.content or ""
            }


        # =================================================
        # ADD ASSISTANT TOOL CALL MESSAGE
        # =================================================

        messages.append(message)


        # =================================================
        # PROCESS TOOL CALLS
        # =================================================

        for tool_call in message.tool_calls:

            tool_name = tool_call.function.name


            # -------------------------------------------------
            # Parse arguments
            # -------------------------------------------------

            try:

                arguments = json.loads(
                    tool_call.function.arguments
                )

            except json.JSONDecodeError:

                arguments = {}


            # -------------------------------------------------
            # Find tool
            # -------------------------------------------------

            function = TOOL_FUNCTIONS.get(
                tool_name
            )


            if not function:

                result = {
                    "success": False,
                    "error": f"Unknown security tool: {tool_name}"
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


            # =================================================
            # SEND TOOL RESULT BACK TO GROQ
            # =================================================

            messages.append({

                "role": "tool",

                "tool_call_id":
                    tool_call.id,

                "content":
                    json.dumps(
                        result,
                        default=str
                    )
            })


# =========================================================
# CLI TEST
# =========================================================

if __name__ == "__main__":

    print("\nSecurity Agent")
    print("==============")
    print("Type 'exit' to quit.\n")

    while True:

        task = input("Security > ")

        if task.lower() in ["exit", "quit"]:
            break

        try:

            result = run_agent(task)

            print("\n" + result["response"])
            print()

        except Exception as e:

            print(
                f"\nERROR: {e}\n"
            )
