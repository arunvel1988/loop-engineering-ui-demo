from groq import Groq
import json

from tools import (
    check_server,
    check_processes,
    check_ports,
    check_docker
)


client = Groq()

MODEL = "openai/gpt-oss-120b"


TOOLS = [

    {
        "type": "function",

        "function": {

            "name": "check_server",

            "description":
                "Check CPU, memory and disk usage.",

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
                "Find processes consuming high CPU or memory.",

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

            "description":
                "Show network ports currently listening.",

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

            "description":
                "Show running Docker containers.",

            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    }
]


TOOL_FUNCTIONS = {

    "check_server":
        check_server,

    "check_processes":
        check_processes,

    "check_ports":
        check_ports,

    "check_docker":
        check_docker
}


def run_agent(task):

    messages = [

        {
            "role": "system",

            "content": """
You are a DevOps Agent.

You investigate infrastructure and
application problems.

Use the available tools to obtain
real information from the server.

Never invent infrastructure information.

Use multiple tools when necessary.
"""
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


        # =====================================
        # MODEL FINISHED
        # =====================================

        if not message.tool_calls:

            return {
                "response":
                    message.content
            }


        # =====================================
        # MODEL REQUESTED TOOL(S)
        # =====================================

        messages.append(message)


        for tool_call in message.tool_calls:

            name = tool_call.function.name

            function = TOOL_FUNCTIONS.get(name)


            if function is None:

                result = {
                    "error":
                        f"Unknown tool: {name}"
                }

            else:

                result = function()


            messages.append({

                "role": "tool",

                "tool_call_id":
                    tool_call.id,

                "content":
                    json.dumps(result)

            })
