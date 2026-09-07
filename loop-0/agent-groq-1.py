from groq import Groq

MODEL = "openai/gpt-oss-120b"

client = Groq()


def run_agent(task):

    completion = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "user",
                "content": task
            }
        ],
        temperature=0.2,
        max_completion_tokens=2048,
        reasoning_effort="medium",
        stream=False
    )

    answer = completion.choices[0].message.content

    return {
        "response": answer
    }
