import requests

OLLAMA = "http://localhost:11434/api/chat"

MODEL = "qwen3:8b"


def run_agent(task):

    payload = {

        "model": MODEL,

        "messages": [

            {
                "role":"user",

                "content": task
            }

        ],

        "stream": False
    }

    response = requests.post(

        OLLAMA,

        json=payload

    )

    answer = response.json()["message"]["content"]

    return {

        "response": answer
    }
