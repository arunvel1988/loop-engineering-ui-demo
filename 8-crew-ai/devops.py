import os

# =========================================================
# GROQ / CREWAI COMPATIBILITY FIX
# =========================================================
#
# CrewAI may add "cache_breakpoint" to the system message.
# Groq currently rejects that field for this model.
#
# This prevents CrewAI from adding the cache breakpoint.
# =========================================================

import crewai.llms.cache as crewai_cache

crewai_cache.mark_cache_breakpoint = lambda msg: msg


# =========================================================
# CREWAI
# =========================================================

from crewai import Agent, Task, Crew, Process, LLM


# =========================================================
# GROQ CONFIGURATION
# =========================================================

if not os.getenv("GROQ_API_KEY"):
    raise RuntimeError(
        "GROQ_API_KEY is not set.\n"
        "Run:\n"
        'export GROQ_API_KEY="gsk_..."'
    )


MODEL = "groq/openai/gpt-oss-120b"


# =========================================================
# LLM
# =========================================================

llm = LLM(
    model=MODEL,
    temperature=0.2,
)


# =========================================================
# AGENT 1
# =========================================================

investigator = Agent(

    role="DevOps Incident Investigator",

    goal="""
    Investigate infrastructure incidents and identify
    the most likely root cause using the available evidence.
    """,

    backstory="""
    You are an experienced DevOps and Site Reliability
    Engineer.

    You investigate:

    - CPU problems
    - Memory problems
    - Disk problems
    - Application failures
    - Docker problems
    - Kubernetes problems

    You always explain your findings using evidence.
    You never blindly assume the root cause.
    """,

    llm=llm,

    verbose=True,
)


# =========================================================
# AGENT 2
# =========================================================

remediator = Agent(

    role="DevOps Remediation Engineer",

    goal="""
    Create a safe and practical remediation plan based
    on the incident investigation.
    """,

    backstory="""
    You are a senior Site Reliability Engineer.

    You review incident investigations and recommend
    safe remediation actions.

    You must consider the possibility of production impact.

    Never perform destructive actions without approval.
    """,

    llm=llm,

    verbose=True,
)


# =========================================================
# TASK 1
# =========================================================

investigation_task = Task(

    description="""

    Investigate the following infrastructure incident.

    ==========================================
    SERVER INFORMATION
    ==========================================

    Server ID:
    web-server-003

    Hostname:
    web-server-003

    Environment:
    production

    CPU:
    95%

    Memory:
    62%

    Disk:
    71%


    ==========================================
    RUNNING PROCESSES
    ==========================================

    python3 app.py    -> 85% CPU
    nginx             -> 3% CPU
    docker            -> 2% CPU
    sshd              -> 1% CPU


    ==========================================
    APPLICATION
    ==========================================

    Normal response time:
    200 ms

    Current response time:
    4 seconds


    ==========================================
    YOUR JOB
    ==========================================

    Determine:

    1. What is the most likely root cause?

    2. What evidence supports the conclusion?

    3. What should a DevOps engineer investigate next?

    4. What information is still missing?

    5. What are the risks if the problem is not fixed?


    IMPORTANT:

    Do not execute commands.

    Only perform analysis.
    """,

    expected_output="""

    Provide a structured incident investigation:

    INCIDENT SUMMARY
    ROOT CAUSE
    EVIDENCE
    ADDITIONAL INVESTIGATION
    RISKS
    """,

    agent=investigator,
)


# =========================================================
# TASK 2
# =========================================================

remediation_task = Task(

    description="""

    Review the investigation produced by the
    DevOps Incident Investigator.

    Create a safe remediation plan.

    The remediation plan must contain:

    1. Immediate mitigation

    2. Investigation commands an engineer
       could run

    3. Validation steps

    4. Long-term prevention

    5. Rollback considerations


    IMPORTANT:

    Do not actually execute commands.

    Only provide recommendations.
    """,

    expected_output="""

    Provide a structured remediation plan:

    IMMEDIATE MITIGATION
    INVESTIGATION COMMANDS
    REMEDIATION
    VALIDATION
    ROLLBACK
    LONG-TERM PREVENTION
    """,

    agent=remediator,

    context=[
        investigation_task
    ],
)


# =========================================================
# CREW
# =========================================================

devops_crew = Crew(

    agents=[
        investigator,
        remediator,
    ],

    tasks=[
        investigation_task,
        remediation_task,
    ],

    process=Process.sequential,

    verbose=True,
)


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    print()
    print("=" * 70)
    print("              DEVOPS AI INCIDENT SYSTEM")
    print("=" * 70)
    print()

    print(f"LLM Model: {MODEL}")
    print("Agents: Investigator + Remediation Engineer")
    print("Process: Sequential")
    print()

    try:

        result = devops_crew.kickoff()

        print()
        print("=" * 70)
        print("                    FINAL RESULT")
        print("=" * 70)
        print()

        print(result)

    except Exception as e:

        print()
        print("=" * 70)
        print("                    ERROR")
        print("=" * 70)
        print()

        print(type(e).__name__)
        print(e)

        raise
