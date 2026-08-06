from gmail_tools import (
    get_unread_emails,
    send_reply,
    send_email,
    trash_email,
    mark_as_read,
)
from ollama_client import ask_planner
from ollama_client import summarize_emails
from ollama_client import draft_reply


def run_agent(goal):

    context = []

    loops = []

    emails = []

    filtered_emails = []

    summary = ""

    drafts = {}  # email_id -> drafted reply body, so SEND_REPLY can reuse it

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

            if emails:

                ids_preview = ", ".join(
                    f"{e.get('id')}:{e.get('subject', '')[:30]}" for e in emails
                )

                observation += f" IDs: [{ids_preview}]"

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

            if filtered_emails:

                ids_preview = ", ".join(
                    f"{e.get('id')}:{e.get('subject', '')[:30]}" for e in filtered_emails
                )

                observation += f" IDs: [{ids_preview}]"

        # --------------------------------------------------
        # SUMMARIZE
        # --------------------------------------------------

        elif action == "SUMMARIZE":

            summary = summarize_emails(goal, filtered_emails)

            observation = "Summary generated successfully."

        # --------------------------------------------------
        # DRAFT REPLY  (generate text only, does not send)
        # --------------------------------------------------

        elif action == "DRAFT_REPLY":

            email_id = arguments.get("email_id")
            instructions = arguments.get("instructions", "")

            pool = filtered_emails or emails

            target = next((e for e in pool if str(e.get("id")) == str(email_id)), None)

            if target is None:

                observation = f"Could not find email with id={email_id!r} to draft a reply for."

            else:

                body = draft_reply(goal, target, instructions)

                drafts[str(email_id)] = body

                preview = body[:120].replace("\n", " ")

                observation = (
                    f"Draft reply created for email id={email_id} "
                    f"(from {target.get('from')}). Preview: \"{preview}...\""
                )

        # --------------------------------------------------
        # SEND REPLY  (actually sends; uses draft if present)
        # --------------------------------------------------

        elif action == "SEND_REPLY":

            email_id = arguments.get("email_id")
            body = arguments.get("body") or drafts.get(str(email_id))

            pool = filtered_emails or emails

            target = next((e for e in pool if str(e.get("id")) == str(email_id)), None)

            if target is None:

                observation = f"Could not find email with id={email_id!r} to reply to."

            elif not body:

                observation = (
                    f"No draft or body available for email id={email_id}. "
                    f"Run DRAFT_REPLY first or supply 'body' in arguments."
                )

            else:

                send_reply(
                    to=target.get("from"),
                    subject="Re: " + target.get("subject", ""),
                    body=body,
                    in_reply_to=target.get("id"),
                    thread_id=target.get("threadId"),
                )

                observation = f"Reply sent to {target.get('from')} for email id={email_id}."

        # --------------------------------------------------
        # SEND EMAIL  (brand-new email, not a reply)
        # --------------------------------------------------

        elif action == "SEND_EMAIL":

            to = arguments.get("to")
            subject = arguments.get("subject")
            body = arguments.get("body")

            if not to or not subject or not body:

                observation = "SEND_EMAIL requires 'to', 'subject', and 'body' arguments."

            else:

                send_email(to=to, subject=subject, body=body)

                observation = f"Email sent to {to} with subject '{subject}'."

        # --------------------------------------------------
        # TRASH EMAIL
        # --------------------------------------------------

        elif action == "TRASH_EMAIL":

            email_id = arguments.get("email_id")

            pool = filtered_emails or emails

            target = next((e for e in pool if str(e.get("id")) == str(email_id)), None)

            if target is None:

                observation = f"Could not find email with id={email_id!r} to trash."

            else:

                trash_email(email_id)

                observation = f"Email id={email_id} moved to Trash."

        # --------------------------------------------------
        # MARK AS READ
        # --------------------------------------------------

        elif action == "MARK_AS_READ":

            email_id = arguments.get("email_id")

            pool = filtered_emails or emails

            target = next((e for e in pool if str(e.get("id")) == str(email_id)), None)

            if target is None:

                observation = f"Could not find email with id={email_id!r} to mark as read."

            else:

                mark_as_read(email_id)

                observation = f"Email id={email_id} marked as read."

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

        "summary": summary,

        "drafts": drafts

    }
