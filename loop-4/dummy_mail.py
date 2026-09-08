import random

EMAILS = [

    {
        "id": 1,
        "from": "clientA@amazon.com",
        "subject": "URGENT - Production API Down",
        "body": """
Production API is returning HTTP 500.
Customers cannot place orders.
Please investigate immediately.
""",
        "priority": "HIGH"
    },

    {
        "id": 2,
        "from": "boss@company.com",
        "subject": "Tomorrow's Loop Engineering Demo",
        "body": """
Please prepare the Loop Engineering demo.
Meeting starts at 10 AM.
Bring the architecture diagram.
""",
        "priority": "MEDIUM"
    },

    {
        "id": 3,
        "from": "newsletter@tech.com",
        "subject": "Weekend Cloud Offers",
        "body": """
Get 50% discount on AWS and Azure certifications.
Offer ends Sunday.
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
Book the hotel before Friday.
""",
        "priority": "LOW"
    },

    {
        "id": 6,
        "from": "security@company.com",
        "subject": "Critical Security Alert",
        "body": """
Multiple failed SSH login attempts detected.
Immediate investigation required.
""",
        "priority": "HIGH"
    },

    {
        "id": 7,
        "from": "hr@company.com",
        "subject": "Annual Leave Balance",
        "body": """
Your annual leave balance has been updated.
Please review before month end.
""",
        "priority": "LOW"
    },

    {
        "id": 8,
        "from": "aws@amazon.com",
        "subject": "AWS Billing Notification",
        "body": """
Your AWS bill exceeded this month's budget.
Review the billing dashboard.
""",
        "priority": "HIGH"
    },

    {
        "id": 9,
        "from": "github@github.com",
        "subject": "Pull Request Review",
        "body": """
A new pull request is waiting for your review.
Repository: loop-engineering-demo.
""",
        "priority": "MEDIUM"
    },

    {
        "id": 10,
        "from": "meeting@company.com",
        "subject": "Architecture Review Meeting",
        "body": """
Architecture review meeting scheduled tomorrow at 3 PM.
Conference Room A.
""",
        "priority": "MEDIUM"
    },

    {
        "id": 11,
        "from": "finance@company.com",
        "subject": "Expense Reimbursement Approved",
        "body": """
Your reimbursement request has been approved.
Payment will be processed tomorrow.
""",
        "priority": "LOW"
    },

    {
        "id": 12,
        "from": "devops@company.com",
        "subject": "Kubernetes Cluster Upgrade",
        "body": """
Production Kubernetes cluster upgrade scheduled tonight.
Verify application readiness before deployment.
""",
        "priority": "HIGH"
    },

    {
        "id": 13,
        "from": "sales@company.com",
        "subject": "Quarterly Sales Report",
        "body": """
Quarterly sales report is now available.
Please review before Friday.
""",
        "priority": "MEDIUM"
    },

    {
        "id": 14,
        "from": "newsletter@docker.com",
        "subject": "Docker Weekly Newsletter",
        "body": """
Latest Docker releases, tutorials and community updates.
""",
        "priority": "LOW"
    },

    {
        "id": 15,
        "from": "customer@flipkart.com",
        "subject": "Order Delivery Delayed",
        "body": """
Customer has reported a delayed shipment.
Please provide an updated delivery estimate.
""",
        "priority": "HIGH"
    }

]


def get_unread_emails():

    """
    Simulates Gmail.
    Every run returns all unread emails.
    """

    return EMAILS


def get_email_by_id(email_id):

    """
    Returns a single email by ID.
    """

    for email in EMAILS:

        if email["id"] == email_id:

            return email

    return None


def mark_as_read(email_id):

    """
    Simulates marking an email as read.
    """

    email = get_email_by_id(email_id)

    if email:

        print(f"Email {email_id} marked as read.")

    else:

        print(f"Email {email_id} not found.")


if __name__ == "__main__":

    print("=" * 60)
    print("Dummy Gmail Inbox")
    print("=" * 60)

    for email in get_unread_emails():

        print(f"ID       : {email['id']}")
        print(f"From     : {email['from']}")
        print(f"Subject  : {email['subject']}")
        print(f"Priority : {email['priority']}")
        print("-" * 60)
