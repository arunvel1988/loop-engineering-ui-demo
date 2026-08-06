import base64
import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


def authenticate():

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

            creds = flow.run_local_server(port=0)

        with open("token.json", "w") as token:
            token.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def get_email_body(payload):

    if "parts" in payload:

        for part in payload["parts"]:

            if part["mimeType"] == "text/plain":

                data = part["body"].get("data")

                if data:
                    return base64.urlsafe_b64decode(
                        data
                    ).decode()

    else:

        data = payload["body"].get("data")

        if data:
            return base64.urlsafe_b64decode(
                data
            ).decode()

    return ""


def get_latest_emails(service, count=10):

    response = service.users().messages().list(
        userId="me",
        maxResults=count
    ).execute()

    messages = response.get("messages", [])

    emails = []

    for msg in messages:

        email = service.users().messages().get(
            userId="me",
            id=msg["id"],
            format="full"
        ).execute()

        headers = email["payload"]["headers"]

        sender = ""
        subject = ""

        for h in headers:

            if h["name"] == "From":
                sender = h["value"]

            elif h["name"] == "Subject":
                subject = h["value"]

        body = get_email_body(email["payload"])

        emails.append({

            "id": email["id"],
            "from": sender,
            "subject": subject,
            "body": body

        })

    return emails


if __name__ == "__main__":

    gmail = authenticate()

    emails = get_latest_emails(gmail, 10)

    print("=" * 80)
    print("YOUR GMAIL")
    print("=" * 80)

    for email in emails:

        print(f"ID      : {email['id']}")
        print(f"FROM    : {email['from']}")
        print(f"SUBJECT : {email['subject']}")
        print("BODY")
        print(email["body"][:300])
        print("-" * 80)
