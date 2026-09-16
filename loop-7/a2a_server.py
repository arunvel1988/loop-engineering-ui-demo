
import os
import asyncio
import uvicorn

from dotenv import load_dotenv

from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import (
    create_agent_card_routes,
    create_jsonrpc_routes,
)
from a2a.server.tasks import (
    InMemoryTaskStore,
    TaskUpdater,
)

from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentSkill,
)

from a2a.helpers import (
    get_message_text,
    new_task_from_user_message,
    new_text_message,
    new_text_part,
)

from a2a.types.a2a_pb2 import TaskState


# ============================================================
# LOAD ENVIRONMENT VARIABLES
# ============================================================

load_dotenv()


# ============================================================
# IMPORT YOUR EXISTING AGENT
# ============================================================

from agent import run_agent


# ============================================================
# CONFIGURATION
# ============================================================

HOST = os.getenv(
    "A2A_HOST",
    "0.0.0.0"
)

PORT = int(
    os.getenv(
        "A2A_PORT",
        "8080"
    )
)

PUBLIC_BASE_URL = os.getenv(
    "PUBLIC_BASE_URL",
    f"http://localhost:{PORT}"
).rstrip("/")

A2A_API_KEY = os.getenv(
    "A2A_API_KEY",
    "my-super-secret-a2a-key"
)


# ============================================================
# API KEY AUTHENTICATION
# ============================================================

class APIKeyMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request, call_next):

        path = request.url.path

        # ----------------------------------------------------
        # Agent Card
        #
        # AWS needs to discover the agent.
        #
        # We allow the Agent Card without the API key.
        # ----------------------------------------------------

        if path.endswith(
            "/.well-known/agent-card.json"
        ):
            return await call_next(request)

        # ----------------------------------------------------
        # Health check
        # ----------------------------------------------------

        if path == "/health":
            return await call_next(request)

        # ----------------------------------------------------
        # A2A API authentication
        # ----------------------------------------------------

        api_key = request.headers.get(
            "x-api-key"
        )

        if api_key != A2A_API_KEY:

            return JSONResponse(
                {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32001,
                        "message": "Unauthorized"
                    }
                },
                status_code=401
            )

        return await call_next(request)


# ============================================================
# INFRASTRUCTURE AGENT EXECUTOR
# ============================================================

class InfrastructureAgentExecutor(
    AgentExecutor
):
    """
    A2A adapter for the existing infrastructure agent.

    IMPORTANT:

    This class does NOT contain the LLM.

    It simply receives an A2A message and passes
    the text to the existing:

        run_agent()

    function from agent.py.
    """

    # ========================================================
    # EXECUTE
    # ========================================================

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:

        # ----------------------------------------------------
        # Create task if required
        # ----------------------------------------------------

        if context.current_task:

            task = context.current_task

        else:

            task = new_task_from_user_message(
                context.message
            )

            await event_queue.enqueue_event(
                task
            )

        # ----------------------------------------------------
        # Task updater
        # ----------------------------------------------------

        task_updater = TaskUpdater(
            event_queue=event_queue,
            task_id=task.id,
            context_id=task.context_id,
        )

        # ----------------------------------------------------
        # Tell caller that investigation started
        # ----------------------------------------------------

        await task_updater.update_status(
            state=TaskState.TASK_STATE_WORKING,
            message=new_text_message(
                "Infrastructure Agent is investigating the request."
            ),
        )

        # ----------------------------------------------------
        # Extract user message
        # ----------------------------------------------------

        query = get_message_text(
            context.message
        )

        if not query:

            response_text = (
                "No text was provided in the A2A request."
            )

        else:

            print()
            print("=" * 70)
            print("A2A REQUEST RECEIVED")
            print("=" * 70)
            print()
            print(query)
            print()
            print("=" * 70)
            print()

            try:

                # ====================================================
                # THIS IS THE IMPORTANT PART
                # ====================================================
                #
                # We call your existing infrastructure agent.
                #
                # AWS DevOps Agent
                #       |
                #       | A2A
                #       v
                # a2a_server.py
                #       |
                #       v
                # run_agent(query)
                #       |
                #       v
                # agent.py
                #
                # ====================================================

                result = await asyncio.to_thread(
                    run_agent,
                    query
                )

                # ----------------------------------------------------
                # Existing run_agent() returns a dictionary
                # ----------------------------------------------------

                if isinstance(
                    result,
                    dict
                ):

                    response_text = result.get(
                        "response",
                        ""
                    )

                    # ------------------------------------------------
                    # Check if remediation is waiting for approval
                    # ------------------------------------------------

                    pending_action = result.get(
                        "pending_action"
                    )

                    if pending_action:

                        response_text += (
                            "\n\n"
                            "REMEDIATION REQUIRES HUMAN APPROVAL\n"
                            "\n"
                            f"Tool: "
                            f"{pending_action.get('tool')}\n"
                            "\n"
                            f"Arguments: "
                            f"{pending_action.get('arguments')}\n"
                            "\n"
                            f"Description: "
                            f"{pending_action.get('description')}\n"
                        )

                    # ------------------------------------------------
                    # Include error
                    # ------------------------------------------------

                    if result.get("error"):

                        response_text += (
                            "\n\n"
                            "Agent Error:\n"
                            f"{result.get('error')}"
                        )

                else:

                    response_text = str(
                        result
                    )

            except Exception as exc:

                print()
                print(
                    "ERROR FROM INFRASTRUCTURE AGENT:"
                )
                print(
                    str(exc)
                )
                print()

                response_text = (
                    "Infrastructure agent failed:\n"
                    f"{str(exc)}"
                )

        # ----------------------------------------------------
        # Safety fallback
        # ----------------------------------------------------

        if not response_text:

            response_text = (
                "The infrastructure agent "
                "did not return a response."
            )

        # ----------------------------------------------------
        # Add final answer as artifact
        # ----------------------------------------------------

        await task_updater.add_artifact(
            parts=[
                new_text_part(
                    text=response_text,
                    media_type="text/plain",
                )
            ]
        )

        # ----------------------------------------------------
        # Mark task completed
        # ----------------------------------------------------

        await task_updater.update_status(
            state=TaskState.TASK_STATE_COMPLETED,
            message=new_text_message(
                "Infrastructure investigation completed."
            ),
        )

        print()
        print("=" * 70)
        print("A2A REQUEST COMPLETED")
        print("=" * 70)
        print()


    # ========================================================
    # CANCEL
    # ========================================================

    async def cancel(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:

        print(
            "A2A cancellation requested."
        )

        await event_queue.enqueue_event(
            new_text_message(
                "Infrastructure investigation cancelled."
            )
        )


# ============================================================
# AGENT SKILL
# ============================================================

infrastructure_skill = AgentSkill(

    id="infrastructure-investigation",

    name="Infrastructure Investigation",

    description=(
        "Investigates infrastructure incidents using "
        "real Linux server telemetry, CPU and memory "
        "information, process information, network "
        "ports, Docker state and historical incident "
        "evidence. Identifies evidence-based root "
        "causes and recommends safe remediation."
    ),

    tags=[
        "devops",
        "sre",
        "infrastructure",
        "incident-response",
        "rca",
        "linux",
        "ec2",
        "docker",
        "cpu",
        "memory",
        "process",
    ],

    input_modes=[
        "text/plain"
    ],

    output_modes=[
        "text/plain"
    ],

    examples=[
        "Investigate why CPU usage is high.",

        "Investigate the current EC2 server.",

        "Find the process consuming excessive CPU.",

        "Check the current Docker containers.",

        "Perform an infrastructure RCA.",

        "Investigate this infrastructure incident "
        "without making changes.",
    ],
)


# ============================================================
# AGENT CARD
# ============================================================

agent_card = AgentCard(

    name="OpenSource Infrastructure Agent",

    description=(
        "An infrastructure incident investigation "
        "agent capable of inspecting Linux server "
        "telemetry, processes, network ports, Docker "
        "containers and historical incident data. "
        "The agent performs evidence-based investigation "
        "and can propose remediation actions that require "
        "human approval."
    ),

    version="1.0.0",

    default_input_modes=[
        "text/plain"
    ],

    default_output_modes=[
        "text/plain"
    ],

    capabilities=AgentCapabilities(
        streaming=False,
        extended_agent_card=False,
    ),

    supported_interfaces=[

        AgentInterface(

            protocol_binding="JSONRPC",

            url=f"{PUBLIC_BASE_URL}/a2a",

            protocol_version="1.0",
        )
    ],

    skills=[
        infrastructure_skill
    ],
)


# ============================================================
# REQUEST HANDLER
# ============================================================

request_handler = DefaultRequestHandler(

    agent_executor=InfrastructureAgentExecutor(),

    task_store=InMemoryTaskStore(),

    agent_card=agent_card,
)


# ============================================================
# A2A ROUTES
# ============================================================

routes = []


# ------------------------------------------------------------
# Agent Card
#
# /.well-known/agent-card.json
# ------------------------------------------------------------

routes.extend(
    create_agent_card_routes(
        agent_card
    )
)


# ------------------------------------------------------------
# JSON-RPC A2A endpoint
#
# /a2a
# ------------------------------------------------------------

routes.extend(
    create_jsonrpc_routes(
        request_handler,
        rpc_url="/a2a",
    )
)


# ============================================================
# STARLETTE APPLICATION
# ============================================================

app = Starlette(
    routes=routes
)


# ============================================================
# AUTHENTICATION MIDDLEWARE
# ============================================================

app.add_middleware(
    APIKeyMiddleware
)


# ============================================================
# HEALTH ENDPOINT
# ============================================================

@app.route(
    "/health",
    methods=["GET"]
)
async def health(request):

    return JSONResponse(
        {
            "status": "healthy",
            "agent": "OpenSource Infrastructure Agent",
            "protocol": "A2A",
            "protocol_version": "1.0",
        }
    )


# ============================================================
# START SERVER
# ============================================================

if __name__ == "__main__":

    print()
    print("=" * 70)
    print("OPEN-SOURCE INFRASTRUCTURE A2A AGENT")
    print("=" * 70)
    print()

    print(
        f"Listening on:"
    )

    print(
        f"http://{HOST}:{PORT}"
    )

    print()

    print(
        "Health:"
    )

    print(
        f"{PUBLIC_BASE_URL}/health"
    )

    print()

    print(
        "Agent Card:"
    )

    print(
        f"{PUBLIC_BASE_URL}/.well-known/agent-card.json"
    )

    print()

    print(
        "A2A endpoint:"
    )

    print(
        f"{PUBLIC_BASE_URL}/a2a"
    )

    print()

    print(
        "Skill:"
    )

    print(
        "Infrastructure Investigation"
    )

    print()

    print("=" * 70)
    print()

    uvicorn.run(
        app,
        host=HOST,
        port=PORT,
    )
