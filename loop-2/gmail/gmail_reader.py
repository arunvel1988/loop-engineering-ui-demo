import os
import base64
from email.mime.text import MIMEText

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

_service = None


def authenticate():
    global _service

    if _service:
        return _service

    creds = None

    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file(
            "token.json",
            SCOPES
        )

    if not creds or not creds.valid:

        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json",
                SCOPES
            )
            creds = flow.run_local_server(
                host="localhost",
                port=8080,
                open_browser=False
            )

        with open("token.json", "w") as token:
            token.write(creds.to_json())

    _service = build("gmail", "v1", credentials=creds)
    return _service


def _header(headers, name):
    for h in headers:
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


def _body(payload):
    if "parts" in payload:
        for part in payload["parts"]:
            if part["mimeType"] == "text/plain":
                data = part["body"].get("data")
                if data:
                    return base64.urlsafe_b64decode(data).decode(errors="ignore")

        for part in payload["parts"]:
            if "parts" in part:
                txt = _body(part)
                if txt:
                    return txt
    else:
        data = payload.get("body", {}).get("data")
        if data:
            return base64.urlsafe_b64decode(data).decode(errors="ignore")

    return ""


def get_unread_emails(max_results=10):

    service = authenticate()

    results = service.users().messages().list(
        userId="me",
        labelIds=["UNREAD"],
        maxResults=max_results
    ).execute()

    msgs = results.get("messages", [])

    emails = []

    for m in msgs:

        msg = service.users().messages().get(
            userId="me",
            id=m["id"],
            format="full"
        ).execute()

        headers = msg["payload"]["headers"]

        emails.append({

            "id": msg["id"],
            "threadId": msg["threadId"],
            "from": _header(headers, "From"),
            "to": _header(headers, "To"),
            "subject": _header(headers, "Subject"),
            "date": _header(headers, "Date"),
            "body": _body(msg["payload"])

        })

    return emails


def get_email_by_id(email_id):

    service = authenticate()

    msg = service.users().messages().get(
        userId="me",
        id=email_id,
        format="full"
    ).execute()

    headers = msg["payload"]["headers"]

    return {

        "id": msg["id"],
        "threadId": msg["threadId"],
        "from": _header(headers, "From"),
        "to": _header(headers, "To"),
        "subject": _header(headers, "Subject"),
        "date": _header(headers, "Date"),
        "body": _body(msg["payload"])

    }


def mark_as_read(email_id):

    service = authenticate()

    service.users().messages().modify(
        userId="me",
        id=email_id,
        body={"removeLabelIds": ["UNREAD"]}
    ).execute()

    return True


def delete_email(email_id):

    service = authenticate()

    service.users().messages().trash(
        userId="me",
        id=email_id
    ).execute()

    return True


def send_email(to, subject, body):

    service = authenticate()

    message = MIMEText(body)

    message["to"] = to
    message["subject"] = subject

    raw = base64.urlsafe_b64encode(
        message.as_bytes()
    ).decode()

    service.users().messages().send(
        userId="me",
        body={"raw": raw}
    ).execute()

    return True


def reply_email(email_id, reply_body):

    service = authenticate()

    original = service.users().messages().get(
        userId="me",
        id=email_id,
        format="metadata",
        metadataHeaders=["From", "Subject", "Message-ID"]
    ).execute()

    headers = original["payload"]["headers"]

    sender = _header(headers, "From")
    subject = _header(headers, "Subject")
    message_id = _header(headers, "Message-ID")

    if not subject.lower().startswith("re:"):
        subject = "Re: " + subject

    message = MIMEText(reply_body)

    message["to"] = sender
    message["subject"] = subject
    message["In-Reply-To"] = message_id
    message["References"] = message_id

    raw = base64.urlsafe_b64encode(
        message.as_bytes()
    ).decode()

    service.users().messages().send(
        userId="me",
        body={
            "raw": raw,
            "threadId": original["threadId"]
        }
    ).execute()

    return True


def search_email(query, max_results=10):

    service = authenticate()

    results = service.users().messages().list(
        userId="me",
        q=query,
        maxResults=max_results
    ).execute()

    messages = results.get("messages", [])

    output = []

    for m in messages:
        output.append(get_email_by_id(m["id"]))

    return output


if __name__ == "__main__":

    emails = get_unread_emails()

    print("=" * 70)

    for email in emails:

        print("ID      :", email["id"])
        print("FROM    :", email["from"])
        print("SUBJECT :", email["subject"])
        print("-" * 70)
