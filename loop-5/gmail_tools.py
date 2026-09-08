"""
gmail_tools.py

A (near) complete Gmail toolkit built on the Gmail API. Covers everything
you'd normally do by hand in Gmail: read, search, reply, forward, compose
new, manage drafts, labels, archive/trash/delete, star, mark read/unread,
threads, and attachments.

Drop-in for your agent: `from gmail_tools import get_unread_emails, send_reply`
still works exactly as before - everything else is additive.

--------------------------------------------------------------------
ONE-TIME SETUP
--------------------------------------------------------------------
1. pip install --upgrade google-auth google-auth-oauthlib google-api-python-client

2. https://console.cloud.google.com/
   - Create/select a project.
   - Enable the "Gmail API".
   - Credentials -> Create Credentials -> OAuth client ID -> Desktop app.
   - Download JSON, save next to this file as: credentials.json

3. First call to any function triggers a browser login; after that a
   token.json is cached locally and auto-refreshes.

4. SCOPES below covers read/send/modify/label/full management. If you
   ever change SCOPES, delete token.json and re-authorize.
--------------------------------------------------------------------
"""

import base64
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.compose",
]

CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token.json"

_service = None


# ============================================================
# AUTH
# ============================================================

def _get_service():
    global _service
    if _service is not None:
        return _service

    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=8080, open_browser=False)
        with open(TOKEN_FILE, "w") as token_file:
            token_file.write(creds.to_json())

    _service = build("gmail", "v1", credentials=creds)
    return _service


# ============================================================
# INTERNAL HELPERS
# ============================================================

def _get_header(headers, name):
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


def _extract_body(payload):
    """Recursively pull plain-text body out of a Gmail message payload."""
    if payload.get("mimeType") == "text/plain" and "data" in payload.get("body", {}):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")

    for part in payload.get("parts", []) or []:
        text = _extract_body(part)
        if text:
            return text

    data = payload.get("body", {}).get("data")
    if data:
        return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
    return ""


def _extract_attachments_meta(payload, out=None):
    """Recursively collect attachment metadata (filename, attachmentId, mimeType)."""
    if out is None:
        out = []
    if payload.get("filename"):
        body = payload.get("body", {})
        if body.get("attachmentId"):
            out.append({
                "filename": payload["filename"],
                "mimeType": payload.get("mimeType"),
                "attachmentId": body["attachmentId"],
            })
    for part in payload.get("parts", []) or []:
        _extract_attachments_meta(part, out)
    return out


def _message_to_dict(msg):
    headers = msg["payload"].get("headers", [])
    body = _extract_body(msg["payload"]) or msg.get("snippet", "")
    label_ids = msg.get("labelIds", [])
    return {
        "id": msg["id"],
        "threadId": msg["threadId"],
        "from": _get_header(headers, "From"),
        "to": _get_header(headers, "To"),
        "subject": _get_header(headers, "Subject"),
        "date": _get_header(headers, "Date"),
        "body": body.strip(),
        "snippet": msg.get("snippet", ""),
        "labelIds": label_ids,
        "priority": "HIGH" if "IMPORTANT" in label_ids else "NORMAL",
        "unread": "UNREAD" in label_ids,
        "starred": "STARRED" in label_ids,
        "attachments": _extract_attachments_meta(msg["payload"]),
    }


def _build_mime_message(to, subject, body, cc=None, bcc=None, attachments=None):
    if attachments:
        message = MIMEMultipart()
        message.attach(MIMEText(body))
        for path in attachments:
            with open(path, "rb") as f:
                part = MIMEApplication(f.read(), Name=os.path.basename(path))
            part["Content-Disposition"] = f'attachment; filename="{os.path.basename(path)}"'
            message.attach(part)
    else:
        message = MIMEText(body)

    message["to"] = to
    message["subject"] = subject
    if cc:
        message["cc"] = cc
    if bcc:
        message["bcc"] = bcc
    return message


# ============================================================
# READING / SEARCHING
# ============================================================

def get_unread_emails(max_results=10, query="is:unread in:inbox"):
    """List unread inbox emails. Returns list of dicts (see _message_to_dict)."""
    return search_emails(query=query, max_results=max_results)


def search_emails(query, max_results=10):
    """
    General-purpose search using Gmail's query syntax, e.g.:
      "from:boss@company.com is:unread"
      "subject:invoice after:2026/07/01"
      "has:attachment label:receipts"
    """
    service = _get_service()
    results = service.users().messages().list(
        userId="me", q=query, maxResults=max_results
    ).execute()

    stubs = results.get("messages", [])
    emails = []
    for stub in stubs:
        msg = service.users().messages().get(userId="me", id=stub["id"], format="full").execute()
        emails.append(_message_to_dict(msg))
    return emails


def get_email(message_id):
    """Fetch full detail for a single email by id."""
    service = _get_service()
    msg = service.users().messages().get(userId="me", id=message_id, format="full").execute()
    return _message_to_dict(msg)


def get_thread(thread_id):
    """Fetch an entire conversation thread as a list of message dicts, in order."""
    service = _get_service()
    thread = service.users().threads().get(userId="me", id=thread_id, format="full").execute()
    return [_message_to_dict(m) for m in thread.get("messages", [])]


def list_threads(query="in:inbox", max_results=10):
    """List conversation threads matching a query (thread id + snippet)."""
    service = _get_service()
    results = service.users().threads().list(userId="me", q=query, maxResults=max_results).execute()
    return results.get("threads", [])


def download_attachment(message_id, attachment_id, save_path):
    """Download a single attachment (get its attachmentId from get_email()['attachments'])."""
    service = _get_service()
    att = service.users().messages().attachments().get(
        userId="me", messageId=message_id, id=attachment_id
    ).execute()
    data = base64.urlsafe_b64decode(att["data"])
    with open(save_path, "wb") as f:
        f.write(data)
    return save_path


# ============================================================
# SENDING / REPLYING / FORWARDING
# ============================================================

def send_email(to, subject, body, cc=None, bcc=None, attachments=None):
    """Compose and send a brand-new email (not a reply)."""
    service = _get_service()
    message = _build_mime_message(to, subject, body, cc, bcc, attachments)
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    sent = service.users().messages().send(userId="me", body={"raw": raw}).execute()
    return {"gmail_message_id": sent.get("id"), "thread_id": sent.get("threadId")}


def send_reply(to, subject, body, in_reply_to=None, thread_id=None, cc=None, attachments=None):
    """
    Reply within an existing thread. Pass thread_id (from the original
    email dict's "threadId") for correct Gmail threading; subject should
    already be "Re: ..." (agent.py already does this).
    """
    service = _get_service()
    message = _build_mime_message(to, subject, body, cc=cc, attachments=attachments)
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    send_body = {"raw": raw}
    if thread_id:
        send_body["threadId"] = thread_id
    sent = service.users().messages().send(userId="me", body=send_body).execute()
    return {
        "to": to, "subject": subject, "body": body, "in_reply_to": in_reply_to,
        "gmail_message_id": sent.get("id"), "thread_id": sent.get("threadId"),
    }


def forward_email(message_id, to, extra_message=""):
    """Forward an existing email to a new recipient, with an optional note prepended."""
    original = get_email(message_id)
    subject = "Fwd: " + original["subject"]
    body = (
        f"{extra_message}\n\n"
        f"---------- Forwarded message ----------\n"
        f"From: {original['from']}\n"
        f"Date: {original['date']}\n"
        f"Subject: {original['subject']}\n\n"
        f"{original['body']}"
    )
    return send_email(to, subject, body)


# ============================================================
# DRAFTS
# ============================================================

def create_draft(to, subject, body, cc=None, bcc=None):
    service = _get_service()
    message = _build_mime_message(to, subject, body, cc, bcc)
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    draft = service.users().drafts().create(userId="me", body={"message": {"raw": raw}}).execute()
    return draft.get("id")


def list_drafts(max_results=10):
    service = _get_service()
    results = service.users().drafts().list(userId="me", maxResults=max_results).execute()
    return results.get("drafts", [])


def send_draft(draft_id):
    service = _get_service()
    sent = service.users().drafts().send(userId="me", body={"id": draft_id}).execute()
    return {"gmail_message_id": sent.get("id"), "thread_id": sent.get("threadId")}


def delete_draft(draft_id):
    service = _get_service()
    service.users().drafts().delete(userId="me", id=draft_id).execute()


# ============================================================
# MESSAGE STATE (read/unread, star, archive, trash, delete)
# ============================================================

def _modify_labels(message_id, add=None, remove=None):
    service = _get_service()
    body = {}
    if add:
        body["addLabelIds"] = add
    if remove:
        body["removeLabelIds"] = remove
    service.users().messages().modify(userId="me", id=message_id, body=body).execute()


def mark_as_read(message_id):
    _modify_labels(message_id, remove=["UNREAD"])


def mark_as_unread(message_id):
    _modify_labels(message_id, add=["UNREAD"])


def star_email(message_id):
    _modify_labels(message_id, add=["STARRED"])


def unstar_email(message_id):
    _modify_labels(message_id, remove=["STARRED"])


def archive_email(message_id):
    """Remove from inbox but keep in All Mail (Gmail's 'Archive')."""
    _modify_labels(message_id, remove=["INBOX"])


def move_to_inbox(message_id):
    _modify_labels(message_id, add=["INBOX"])


def trash_email(message_id):
    service = _get_service()
    service.users().messages().trash(userId="me", id=message_id).execute()


def untrash_email(message_id):
    service = _get_service()
    service.users().messages().untrash(userId="me", id=message_id).execute()


def delete_email_permanently(message_id):
    """Irreversible. Bypasses Trash entirely - use with caution."""
    service = _get_service()
    service.users().messages().delete(userId="me", id=message_id).execute()


# ============================================================
# LABELS
# ============================================================

def list_labels():
    service = _get_service()
    return service.users().labels().list(userId="me").execute().get("labels", [])


def create_label(name):
    service = _get_service()
    label = service.users().labels().create(
        userId="me", body={"name": name, "labelListVisibility": "labelShow", "messageListVisibility": "show"}
    ).execute()
    return label["id"]


def add_label_to_email(message_id, label_id):
    _modify_labels(message_id, add=[label_id])


def remove_label_from_email(message_id, label_id):
    _modify_labels(message_id, remove=[label_id])
