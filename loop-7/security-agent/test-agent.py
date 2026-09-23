import asyncio
import uuid

from a2a.client import create_client
from a2a.types import Message, Part, Role, SendMessageRequest


async def main():
    print("========================================")
    print("       A2A SECURITY AGENT CLIENT")
    print("========================================")

    print("\nConnecting to Security Agent...")

    client = await create_client("http://localhost:9000")

    print("Connected successfully.")
    print("Sending security audit request...\n")

    message = Message(
        role=Role.ROLE_USER,
        message_id=str(uuid.uuid4()),
        parts=[
            Part(
                text=(
                    "Perform a security audit of this Linux server. "
                    "Check open ports, running processes, failed logins, "
                    "SUID files, and world-writable files."
                )
            )
        ],
    )

    request = SendMessageRequest(
        message=message
    )

    print("Waiting for Security Agent...\n")

    async for response in client.send_message(request):

        print("========================================")
        print("A2A RESPONSE")
        print("========================================")

        if response.HasField("task"):
            print("TASK:")
            print(response.task)

        elif response.HasField("message"):
            print("MESSAGE:")
            print(response.message)

        elif response.HasField("status_update"):
            print("STATUS UPDATE:")
            print(response.status_update)

        elif response.HasField("artifact_update"):
            print("ARTIFACT:")
            print(response.artifact_update)

        print()


if __name__ == "__main__":
    asyncio.run(main())
