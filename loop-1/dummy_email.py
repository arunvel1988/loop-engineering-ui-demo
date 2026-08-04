import random

EMAILS = [

    {
        "id": 1,
        "from": "clientA@amazon.com",
        "subject": "URGENT - Production Down",
        "body": """
Production API is returning HTTP 500.
Customers are unable to place orders.
Please investigate immediately.
""",
        "priority": "HIGH"
    },

    {
        "id": 2,
        "from": "boss@company.com",
        "subject": "Tomorrow's Presentation",
        "body": """
Please prepare the Loop Engineering demo.
Meeting starts at 10 AM.
""",
        "priority": "MEDIUM"
    },

    {
        "id": 3,
        "from": "newsletter@tech.com",
        "subject": "Weekend Offers",
        "body": """
Get 50% discount on cloud certifications.
""",
        "priority": "LOW"
    },

    {
        "id": 4,
        "from": "clientB@microsoft.com",
        "subject": "Invoice Approval Required",
        "body": """
Kindly approve the invoice today.
Finance team is waiting.
""",
        "priority": "HIGH"
    },

    {
        "id": 5,
        "from": "friend@gmail.com",
        "subject": "Goa Trip",
        "body": """
Weekend Goa trip confirmed.
""",
        "priority": "LOW"
    }

]


def get_unread_emails():

    """
    Simulates Gmail.
    Every run returns emails.
    """

    return EMAILS


def mark_as_read(email_id):

    print(f"Email {email_id} marked as read.")
