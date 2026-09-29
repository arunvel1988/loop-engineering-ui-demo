import json
import os
import time

from groq import Groq
from playwright.sync_api import sync_playwright


# ============================================================
# GROQ
# ============================================================

client = Groq(
    api_key=os.environ["GROQ_API_KEY"]
)

MODEL = "openai/gpt-oss-120b"


# ============================================================
# BROWSER CONFIGURATION
# ============================================================

BROWSER_DATA_DIR = os.path.expanduser(
    "~/.personal-agent-browser"
)

browser_context = None
playwright_instance = None


# ============================================================
# START HEADLESS BROWSER
# ============================================================

def start_browser():

    global browser_context
    global playwright_instance

    if browser_context is not None:
        return browser_context

    print()
    print("=" * 70)
    print("STARTING HEADLESS CHROMIUM")
    print("=" * 70)

    playwright_instance = sync_playwright().start()

    browser_context = (
        playwright_instance.chromium
        .launch_persistent_context(

            user_data_dir=BROWSER_DATA_DIR,

            headless=True,

            viewport={
                "width": 1440,
                "height": 900
            },

            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu"
            ]
        )
    )

    print("Browser started.")
    print("Profile:", BROWSER_DATA_DIR)

    return browser_context


# ============================================================
# GET CURRENT PAGE
# ============================================================

def get_page():

    context = start_browser()

    if len(context.pages) == 0:

        page = context.new_page()

    else:

        page = context.pages[0]

    return page


# ============================================================
# BROWSER OPEN
# ============================================================

def browser_open(url):

    page = get_page()

    print()
    print("[BROWSER] Opening:", url)

    page.goto(
        url,
        wait_until="domcontentloaded",
        timeout=60000
    )

    time.sleep(1)

    return {
        "success": True,
        "url": page.url,
        "title": page.title()
    }


# ============================================================
# BROWSER READ
# ============================================================

def browser_read():

    page = get_page()

    print(
        "[BROWSER] Reading:",
        page.url
    )

    try:

        text = page.locator(
            "body"
        ).inner_text(
            timeout=15000
        )

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }

    # Prevent massive pages from consuming Groq context.
    text = text[:20000]

    return {
        "success": True,
        "url": page.url,
        "title": page.title(),
        "content": text
    }


# ============================================================
# BROWSER CLICK
# ============================================================

def browser_click(selector):

    page = get_page()

    print(
        "[BROWSER] Clicking:",
        selector
    )

    try:

        page.locator(
            selector
        ).first.click(
            timeout=30000
        )

        time.sleep(1)

        return {
            "success": True,
            "url": page.url
        }

    except Exception as e:

        return {
            "success": False,
            "error": str(e),
            "url": page.url
        }


# ============================================================
# BROWSER TYPE
# ============================================================

def browser_type(
    selector,
    text
):

    page = get_page()

    print(
        "[BROWSER] Typing into:",
        selector
    )

    try:

        page.locator(
            selector
        ).first.fill(
            text
        )

        return {
            "success": True,
            "selector": selector
        }

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }


# ============================================================
# BROWSER PRESS
# ============================================================

def browser_press(
    selector,
    key
):

    page = get_page()

    try:

        page.locator(
            selector
        ).first.press(
            key
        )

        time.sleep(1)

        return {
            "success": True,
            "url": page.url
        }

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }


# ============================================================
# BROWSER SCREENSHOT
# ============================================================

def browser_screenshot():

    page = get_page()

    path = "/tmp/personal-agent-browser.png"

    try:

        page.screenshot(
            path=path,
            full_page=True
        )

        return {
            "success": True,
            "path": path,
            "url": page.url
        }

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }


# ============================================================
# BROWSER BACK
# ============================================================

def browser_back():

    page = get_page()

    try:

        page.go_back(
            wait_until="domcontentloaded",
            timeout=30000
        )

        return {
            "success": True,
            "url": page.url,
            "title": page.title()
        }

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }


# ============================================================
# HUMAN APPROVAL
# ============================================================

pending_action = None


def request_approval(
    action,
    description
):

    global pending_action

    pending_action = {

        "action": action,

        "description": description,

        "status": "pending"

    }

    print()
    print("=" * 70)
    print("HUMAN APPROVAL REQUIRED")
    print("=" * 70)

    print(
        json.dumps(
            pending_action,
            indent=2
        )
    )

    print("=" * 70)

    return {

        "success": False,

        "requires_approval": True,

        "action": action,

        "description": description,

        "message":
            "Human approval is required before "
            "this action can continue."

    }


# ============================================================
# TOOL DEFINITIONS
# ============================================================

TOOLS = [

    {
        "type": "function",

        "function": {

            "name": "browser_open",

            "description":
                "Open a URL in the headless Chromium browser.",

            "parameters": {

                "type": "object",

                "properties": {

                    "url": {
                        "type": "string",
                        "description":
                            "Complete URL to open."
                    }

                },

                "required": ["url"]

            }

        }

    },

    {
        "type": "function",

        "function": {

            "name": "browser_read",

            "description":
                "Read the visible text from the current webpage.",

            "parameters": {

                "type": "object",

                "properties": {},

                "required": []

            }

        }

    },

    {
        "type": "function",

        "function": {

            "name": "browser_click",

            "description":
                "Click an element on the current webpage "
                "using a CSS selector.",

            "parameters": {

                "type": "object",

                "properties": {

                    "selector": {
                        "type": "string",
                        "description":
                            "CSS selector for the element."
                    }

                },

                "required": ["selector"]

            }

        }

    },

    {
        "type": "function",

        "function": {

            "name": "browser_type",

            "description":
                "Type text into a webpage input using "
                "a CSS selector.",

            "parameters": {

                "type": "object",

                "properties": {

                    "selector": {
                        "type": "string"
                    },

                    "text": {
                        "type": "string"
                    }

                },

                "required": [
                    "selector",
                    "text"
                ]

            }

        }

    },

    {
        "type": "function",

        "function": {

            "name": "browser_press",

            "description":
                "Press a keyboard key on a webpage element.",

            "parameters": {

                "type": "object",

                "properties": {

                    "selector": {
                        "type": "string"
                    },

                    "key": {
                        "type": "string",
                        "description":
                            "Keyboard key such as Enter, Tab, "
                            "Escape, ArrowDown."
                    }

                },

                "required": [
                    "selector",
                    "key"
                ]

            }

        }

    },

    {
        "type": "function",

        "function": {

            "name": "browser_screenshot",

            "description":
                "Take a screenshot of the current webpage.",

            "parameters": {

                "type": "object",

                "properties": {},

                "required": []

            }

        }

    },

    {
        "type": "function",

        "function": {

            "name": "browser_back",

            "description":
                "Navigate the browser back to the previous page.",

            "parameters": {

                "type": "object",

                "properties": {},

                "required": []

            }

        }

    },

    {
        "type": "function",

        "function": {

            "name": "request_approval",

            "description":
                "Request explicit human approval before "
                "a financial, booking, purchase, payment, "
                "email-send, deletion, or other irreversible action.",

            "parameters": {

                "type": "object",

                "properties": {

                    "action": {
                        "type": "string"
                    },

                    "description": {
                        "type": "string"
                    }

                },

                "required": [
                    "action",
                    "description"
                ]

            }

        }

    }

]


# ============================================================
# TOOL MAP
# ============================================================

TOOL_FUNCTIONS = {

    "browser_open":
        browser_open,

    "browser_read":
        browser_read,

    "browser_click":
        browser_click,

    "browser_type":
        browser_type,

    "browser_press":
        browser_press,

    "browser_screenshot":
        browser_screenshot,

    "browser_back":
        browser_back,

    "request_approval":
        request_approval

}


# ============================================================
# SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """

You are a personal AI assistant running on the user's
GCP Ubuntu VM.

You help the user perform personal computer and web tasks.

============================================================
CAPABILITIES
============================================================

You can:

- browse websites
- open URLs
- read webpages
- click webpage elements
- type into webpage fields
- press keyboard keys
- navigate backwards
- take screenshots
- research travel
- research railway information
- navigate websites

============================================================
BROWSER
============================================================

The browser is Chromium running HEADLESS on the GCP VM.

You cannot see the browser visually.

Therefore:

1. Open the website.
2. Read the page.
3. Use the information returned by browser_read.
4. Determine the appropriate selector.
5. Click/type.
6. Read the page again.

Never invent webpage information.

============================================================
LOGIN
============================================================

If a website requires authentication:

DO NOT ask the user to provide their password
to the AI.

Do not store passwords in the agent.

The user must authenticate using an appropriate
authentication mechanism.

If authentication cannot be completed because the
website requires interactive human verification,
stop and tell the user.

============================================================
RAILWAY / TRAVEL
============================================================

You may search for railway/travel options.

You may navigate through the booking process
to the point immediately before final purchase/payment.

You MUST NOT automatically complete:

- payment
- final ticket purchase
- irreversible booking

Before such an action:

CALL request_approval.

============================================================
SENSITIVE ACTIONS
============================================================

Human approval is REQUIRED before:

- buying anything
- booking a ticket
- making payment
- sending an email
- deleting data
- submitting an irreversible form
- changing important account settings

Do NOT execute these actions automatically.

============================================================
READ VS ACTION
============================================================

These normally do not require approval:

- opening websites
- searching
- reading webpages
- comparing prices
- reading public information

These require approval:

- purchase
- booking
- payment
- send
- delete
- irreversible submission

============================================================
BROWSER LOOP
============================================================

For browser tasks use:

OPEN
  ↓
READ
  ↓
DECIDE
  ↓
CLICK / TYPE
  ↓
READ AGAIN
  ↓
DECIDE
  ↓
repeat

Stop when the user's task is complete.

============================================================
IMPORTANT
============================================================

Never invent:

- prices
- train names
- train times
- availability
- account information
- webpage contents
- confirmation numbers

Use browser tools to obtain current information.

"""


# ============================================================
# RUN AGENT
# ============================================================

def run_agent(
    task,
    conversation_history=None,
    conversation_id=None,
    **kwargs
):

    global pending_action

    pending_action = None

    messages = [

        {
            "role": "system",
            "content": SYSTEM_PROMPT
        }

    ]

    # --------------------------------------------------------
    # EXISTING FLASK CHAT HISTORY
    # --------------------------------------------------------

    if conversation_history:

        for item in conversation_history:

            if not isinstance(
                item,
                dict
            ):
                continue

            role = item.get("role")

            content = item.get(
                "content"
            )

            if role and content:

                messages.append({

                    "role": role,

                    "content": content

                })

    # --------------------------------------------------------
    # CURRENT REQUEST
    # --------------------------------------------------------

    messages.append({

        "role": "user",

        "content": task

    })

    # --------------------------------------------------------
    # ORCHESTRATION LOOP
    # --------------------------------------------------------

    for iteration in range(20):

        print()
        print("=" * 70)
        print(
            "AGENT ITERATION:",
            iteration + 1
        )
        print("=" * 70)

        response = client.chat.completions.create(

            model=MODEL,

            messages=messages,

            tools=TOOLS,

            tool_choice="auto",

            temperature=0.2,

            max_completion_tokens=2048,

            reasoning_effort="medium"

        )

        message = (
            response
            .choices[0]
            .message
        )

        # ----------------------------------------------------
        # FINAL RESPONSE
        # ----------------------------------------------------

        if not message.tool_calls:

            return {

                "response":
                    message.content or "",

                "pending_action":
                    pending_action

            }

        # ----------------------------------------------------
        # ADD ASSISTANT TOOL MESSAGE
        # ----------------------------------------------------

        messages.append(message)

        # ----------------------------------------------------
        # TOOL CALLS
        # ----------------------------------------------------

        for tool_call in message.tool_calls:

            tool_name = (
                tool_call.function.name
            )

            raw_arguments = (
                tool_call.function.arguments
                or "{}"
            )

            try:

                arguments = json.loads(
                    raw_arguments
                )

            except Exception:

                arguments = {}

            print()
            print(
                "[AGENT TOOL]",
                tool_name
            )

            print(
                "[ARGUMENTS]",
                arguments
            )

            # ------------------------------------------------
            # TOOL DOES NOT EXIST
            # ------------------------------------------------

            function = TOOL_FUNCTIONS.get(
                tool_name
            )

            if function is None:

                result = {

                    "success": False,

                    "error":
                        f"Unknown tool: {tool_name}"

                }

            else:

                try:

                    result = function(
                        **arguments
                    )

                except Exception as e:

                    print(
                        "[TOOL ERROR]",
                        str(e)
                    )

                    result = {

                        "success": False,

                        "error": str(e)

                    }

            print(
                "[TOOL RESULT]",
                result
            )

            # ------------------------------------------------
            # APPROVAL REQUIRED
            # ------------------------------------------------

            if result.get(
                "requires_approval"
            ):

                return {

                    "response":
                        "I reached an action that "
                        "requires your approval.",

                    "pending_action":
                        result

                }

            # ------------------------------------------------
            # SEND RESULT TO GROQ
            # ------------------------------------------------

            messages.append({

                "role": "tool",

                "tool_call_id":
                    tool_call.id,

                "content":
                    json.dumps(
                        result,
                        default=str
                    )

            })

    # --------------------------------------------------------
    # MAX ITERATIONS
    # --------------------------------------------------------

    return {

        "response":
            "I stopped because the maximum "
            "number of agent steps was reached.",

        "pending_action":
            pending_action

    }


# ============================================================
# CLEAN SHUTDOWN
# ============================================================

def shutdown_browser():

    global browser_context
    global playwright_instance

    try:

        if browser_context:

            browser_context.close()

    finally:

        browser_context = None

    try:

        if playwright_instance:

            playwright_instance.stop()

    finally:

        playwright_instance = None
