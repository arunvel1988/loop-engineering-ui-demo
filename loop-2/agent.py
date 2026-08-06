#from dummy_mail import get_unread_emails
from gmail_tools import (
    get_unread_emails,
    send_reply,
    send_email,
    trash_email,
    mark_as_read,
)
from ollama_client import ask_planner
from ollama_client import summarize_emails


def run_agent(goal):

    context = []

    loops = []

    emails = []

    filtered_emails = []

    summary = ""

    while True:

        planner = ask_planner(goal, context)

        thought = planner["thought"]
        action = planner["action"]

        arguments = planner.get("arguments", {})

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

            filtered_emails = emails

            priority = arguments.get("priority")
            sender = arguments.get("sender")
            keyword = arguments.get("keyword")

            # Filter by Priority
            if priority:

                filtered_emails = [

                    email

                    for email in filtered_emails

                    if email.get("priority", "").upper() == priority.upper()

                ]

            # Filter by Sender
            if sender:

                filtered_emails = [

                    email

                    for email in filtered_emails

                    if sender.lower() in email.get("from", "").lower()

                ]

            # Filter by Keyword
            if keyword:

                filtered_emails = [

                    email

                    for email in filtered_emails

                    if keyword.lower() in (
                        email.get("subject", "") +
                        " " +
                        email.get("body", "")
                    ).lower()

                ]

            observation = f"{len(filtered_emails)} emails matched the requested filter."

        # --------------------------------------------------
        # SUMMARIZE
        # --------------------------------------------------

        elif action == "SUMMARIZE":

            summary = summarize_emails(goal, filtered_emails)

            observation = "Summary generated successfully."

        # --------------------------------------------------
        # SEND SLACK
        # --------------------------------------------------

        elif action == "SEND_SLACK":

            print("\n==============================")
            print("FAKE SLACK MESSAGE")
            print("==============================")
            print(summary)
            print("==============================\n")

            observation = "Summary sent to Slack."

        # --------------------------------------------------
        # DONE
        # --------------------------------------------------

        elif action == "DONE":

            loops.append({

                "thought": thought,

                "action": action,

                "observation": "Workflow completed."

            })

            break

        # --------------------------------------------------
        # UNKNOWN
        # --------------------------------------------------

        else:

            observation = "Unknown action returned by planner."

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

    return {

        "loops": loops,

        "summary": summary

    }
