from dummy_mail import get_unread_emails
from ollama_client import ask_planner
from ollama_client import summarize_emails


def run_agent(goal):

    context = []

    loops = []

    emails = []

    summary = ""

    while True:

        # Ask the Planner
        planner = ask_planner(goal, context)

        thought = planner["thought"]
        action = planner["action"]

        observation = ""

        # --------------------------------------------------
        # READ EMAILS
        # --------------------------------------------------

        if action == "READ_EMAILS":

            emails = get_unread_emails()

            observation = f"{len(emails)} unread emails found."

        # --------------------------------------------------
        # FILTER EMAILS
        # --------------------------------------------------

        elif action == "FILTER_EMAILS":

            important = []

            for email in emails:

                if email["priority"] in ["HIGH", "MEDIUM"]:

                    important.append(email)

            emails = important

            observation = f"{len(emails)} important emails selected."

        # --------------------------------------------------
        # SUMMARIZE
        # --------------------------------------------------

        elif action == "SUMMARIZE":

            summary = summarize_emails(emails)

            observation = "Summary generated successfully."

        # --------------------------------------------------
        # SEND SLACK
        # --------------------------------------------------

        elif action == "SEND_SLACK":

            print("\n========== FAKE SLACK ==========\n")
            print(summary)
            print("\n===============================\n")

            observation = "Summary sent to Slack."

        # --------------------------------------------------
        # DONE
        # --------------------------------------------------

        elif action == "DONE":

            loops.append({

                "thought": thought,

                "action": action,

                "observation": "Workflow Completed"

            })

            break

        else:

            observation = "Unknown Action"

        # --------------------------------------------------

        context.append({

            "action": action,

            "observation": observation

        })

        loops.append({

            "thought": thought,

            "action": action,

            "observation": observation

        })

    return loops
