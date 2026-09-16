import asyncio
import os
import uvicorn

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from a2a.helpers import new_task_from_user_message
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
)

from a2a.types.a2a_pb2 import TaskState

from agent import run_agent


# ============================================================
# CONFIGURATION
# ============================================================

HOST = "0.0.0.0"
PORT = int(os.environ.get("A2A_PORT", "8080"))

# IMPORTANT:
# For local testing, localhost is fine.
#
# Later, when exposing through Killercoda / public URL,
# change this environment variable:
#
# export A2A_PUBLIC_URL="https://YOUR-URL"
#
PUBLIC_URL = os.environ.get(
    "A2A_PUBLIC_URL",
    f"http://127.0.0.1:{PORT}"
)


# ============================================================
# A2A AGENT CARD
# ============================================================

agent_skill = AgentSkill(
    id="infrastructure-investigation",
    name="Infrastructure Investigation",
    description=(
        "Investigates Linux infrastructure incidents using live "
        "CPU, memory, disk, process, port, Docker and historical "
        "incident telemetry. Provides evidence-based root cause "
        "analysis and remediation recommendations."
    ),
    tags=[
        "infrastructure",
        "linux",
        "ec2",
        "incident",
        "root-cause-analysis",
        "devops",
        "sre",
    ],
    examples=[
        "Investigate high CPU usage on the server.",
        "Find the process consuming the most CPU.",
        "Investigate a server incident and determine the root cause.",
        "Check whether Docker containers are causing the incident.",
        "Analyze the current server state and recommend remediation.",
    ],
)


agent_card = AgentCard(
    name="Open Source Infrastructure Agent",
    description=(
        "An infrastructure investigation agent built with Python, "
        "Groq and custom infrastructure tools. It investigates "
        "Linux server incidents, correlates live telemetry with "
        "historical incidents and recommends safe remediation."
    ),
    version="1.0.0",

    default_input_modes=[
        "text",
        "text/plain",
    ],

    default_output_modes=[
        "text",
        "text/plain",
    ],

    capabilities=AgentCapabilities(
        streaming=False,
    ),

    supported_interfaces=[
        AgentInterface(
            protocol_binding="JSONRPC",
            url=f"{PUBLIC_URL}/",
            protocol_version="1.0",
        )
    ],

    skills=[
        agent_skill,
    ],
)


# ============================================================
# A2A EXECUTOR
# ============================================================

class InfrastructureAgentExecutor(AgentExecutor):
    """
    Thin A2A adapter around the existing infrastructure agent.

    We do NOT modify agent.py.

    A2A request
          |
          v
    InfrastructureAgentExecutor
          |
          v
    existing run_agent()
          |
          v
    Groq + infrastructure tools
    """

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:

        try:

            # ------------------------------------------------
            # Extract user message
            # ------------------------------------------------

            user_message = context.message

            query = ""

            if user_message is not None:

                for part in user_message.parts:

                    # A2A v1 Part may contain text
                    if hasattr(part, "root"):

                        root = part.root

                        if hasattr(root, "text") and root.text:
                            query += root.text

                    elif hasattr(part, "text") and part.text:
                        query += part.text

            query = query.strip()

            if not query:
                query = "Investigate the current infrastructure."


            print("\n" + "=" * 70)
            print("A2A REQUEST")
            print("=" * 70)
            print(query)
            print("=" * 70)


            # ------------------------------------------------
            # Run existing infrastructure agent
            # ------------------------------------------------

            result = await asyncio.to_thread(
                run_agent,
                query,
            )


            # ------------------------------------------------
            # Convert result to string
            # ------------------------------------------------

            if isinstance(result, dict):

                response_text = result.get("response")

                if response_text is None:
                    response_text = str(result)

            else:

                response_text = str(result)


            if not response_text:
                response_text = "The infrastructure agent returned no response."


            print("\n" + "=" * 70)
            print("A2A RESPONSE")
            print("=" * 70)
            print(response_text)
            print("=" * 70)


            # ------------------------------------------------
            # Create task
            # ------------------------------------------------
            task = new_task_from_user_message(context.message)
            

            task_id = task.id

            context_id = task.context_id


            # ------------------------------------------------
            # Task updater
            # ------------------------------------------------

            updater = TaskUpdater(
                event_queue=event_queue,
                task_id=task_id,
                context_id=context_id,
            )


            # ------------------------------------------------
            # Send initial task
            # ------------------------------------------------

            await event_queue.enqueue_event(
                task
            )


            # ------------------------------------------------
            # Mark task working
            # ------------------------------------------------

            await updater.update_status(
                state=TaskState.TASK_STATE_WORKING
            )


            # ------------------------------------------------
            # Send final response
            # ------------------------------------------------

            await updater.add_artifact(
                parts=[
                    Part(
                        text=response_text
                    )
                ],
                name="infrastructure-investigation-result",
            )


            # ------------------------------------------------
            # Complete task
            # ------------------------------------------------

            await updater.update_status(
                state=TaskState.TASK_STATE_COMPLETED
            )


        except asyncio.CancelledError:

            raise


        except Exception as exc:

            print("\nA2A EXECUTION ERROR:")
            print(str(exc))

            try:

                # If task/updater was already created,
                # report failure to the A2A client.

                await updater.update_status(
                    state=TaskState.TASK_STATE_FAILED,
                    message=updater.new_agent_message(
                        [
                            Part(
                                text=f"Infrastructure agent error: {exc}"
                            )
                        ]
                    ),
                )

            except Exception:

                # If failure happened before updater creation,
                # simply propagate the exception.

                pass

            raise


    async def cancel(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:

        print(
            f"A2A cancellation requested for "
            f"context={context.context_id}"
        )


# ============================================================
# HEALTH CHECK
# ============================================================

async def health(request):
    return JSONResponse(
        {
            "status": "ok",
            "service": "open-source-infrastructure-agent",
            "a2a": True,
        }
    )


# ============================================================
# BUILD STARLETTE APPLICATION
# ============================================================

def build_app():

    # --------------------------------------------------------
    # A2A request handler
    # --------------------------------------------------------

    request_handler = DefaultRequestHandler(
        agent_executor=InfrastructureAgentExecutor(),
        task_store=InMemoryTaskStore(),
        agent_card=agent_card,
    )


    # --------------------------------------------------------
    # A2A routes
    # --------------------------------------------------------

    routes = []

    # Agent Card
    routes.extend(
        create_agent_card_routes(
            agent_card
        )
    )

    # JSON-RPC A2A endpoint
    #
    # AWS DevOps Agent will communicate with this endpoint.
    #
    routes.extend(
        create_jsonrpc_routes(
            request_handler,
            rpc_url="/",
        )
    )

    # --------------------------------------------------------
    # Health endpoint
    # --------------------------------------------------------

    routes.append(
        Route(
            "/health",
            health,
            methods=["GET"],
        )
    )


    # --------------------------------------------------------
    # Starlette application
    # --------------------------------------------------------

    app = Starlette(
        routes=routes
    )

    return app


# ============================================================
# START SERVER
# ============================================================

app = build_app()


if __name__ == "__main__":

    print()
    print("=" * 70)
    print("OPEN SOURCE INFRASTRUCTURE A2A AGENT")
    print("=" * 70)

    print(f"Listening:       http://{HOST}:{PORT}")
    print(f"Public URL:      {PUBLIC_URL}")

    print()
    print(
        "Agent Card:"
    )

    print(
        f"{PUBLIC_URL}/.well-known/agent-card.json"
    )

    print()
    print(
        "A2A JSON-RPC:"
    )

    print(
        f"{PUBLIC_URL}/"
    )

    print()
    print(
        "Health:"
    )

    print(
        f"{PUBLIC_URL}/health"
    )

    print()
    print("=" * 70)
    print("Existing agent.py will be used unchanged.")
    print("=" * 70)
    print()


    uvicorn.run(
        app,
        host=HOST,
        port=PORT,
    )
