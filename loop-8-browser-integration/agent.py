import os
import json
import time
import atexit
import traceback

from groq import Groq
from playwright.sync_api import sync_playwright


# ============================================================
# GROQ CONFIGURATION
# ============================================================

MODEL = "openai/gpt-oss-120b"

client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)


# ============================================================
# AGENT CONFIGURATION
# ============================================================

MAX_TOOL_ITERATIONS = 20

MAX_SHORT_TERM_MESSAGES = 12

MAX_PAGE_CONTENT_CHARS = 12000

BROWSER_DATA_DIR = os.path.expanduser(
    "~/.personal-agent-browser"
)


# ============================================================
# PENDING HUMAN APPROVAL
# ============================================================

pending_action = None


# ============================================================
# PLAYWRIGHT
# ============================================================

playwright_instance = None
browser_context = None


def start_browser():
    """
    Start persistent headless Chromium.

    The persistent profile allows browser sessions/cookies
    to remain available between requests.
    """

    global playwright_instance
    global browser_context

    if browser_context is not None:
        return browser_context

    os.makedirs(
        BROWSER_DATA_DIR,
        exist_ok=True
    )

    print("Browser started.")
    print(
        f"Profile: {BROWSER_DATA_DIR}"
    )

    playwright_instance = sync_playwright().start()

    browser_context = (
        playwright_instance
        .chromium
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
                "--disable-gpu",
                "--disable-blink-features=AutomationControlled",
            ],
        )
    )

    return browser_context


def get_page():
    """
    Return the active browser page.

    If no page exists, create one.
    """

    context = start_browser()

    pages = context.pages

    if pages:
        return pages[-1]

    return context.new_page()


# Start browser when agent.py is imported.
start_browser()


# ============================================================
# BROWSER TOOL: OPEN
# ============================================================

def browser_open(url: str):
    """
    Open a URL in the current browser page.
    """

    try:

        page = get_page()

        print()
        print(
            f"[BROWSER] Opening: {url}"
        )

        page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=30000
        )

        try:
            page.wait_for_load_state(
                "networkidle",
                timeout=5000
            )
        except Exception:
            pass

        result = {
            "success": True,
            "url": page.url,
            "title": page.title(),
        }

        print(
            f"[BROWSER RESULT] {result}"
        )

        return result

    except Exception as e:

        error = str(e)

        print(
            f"[BROWSER ERROR] {error}"
        )

        return {
            "success": False,
            "error": error,
        }


# ============================================================
# BROWSER TOOL: READ
# ============================================================

def browser_read():
    """
    Read visible text from the current webpage.
    """

    try:

        page = get_page()

        print()
        print(
            f"[BROWSER] Reading: {page.url}"
        )

        # Remove obvious non-content elements.
        try:

            page.evaluate(
                """
                () => {
                    for (const selector of [
                        'script',
                        'style',
                        'noscript'
                    ]) {
                        document
                            .querySelectorAll(selector)
                            .forEach(el => el.remove());
                    }
                }
                """
            )

        except Exception:
            pass

        content = page.locator(
            "body"
        ).inner_text(
            timeout=10000
        )

        content = content.strip()

        if len(content) > MAX_PAGE_CONTENT_CHARS:

            content = (
                content[
                    :MAX_PAGE_CONTENT_CHARS
                ]
                + "\n...[content truncated]"
            )

        result = {
            "success": True,
            "url": page.url,
            "title": page.title(),
            "content": content,
        }

        print(
            f"[BROWSER RESULT] {result}"
        )

        return result

    except Exception as e:

        error = str(e)

        print(
            f"[BROWSER ERROR] {error}"
        )

        return {
            "success": False,
            "error": error,
        }


# ============================================================
# BROWSER TOOL: FIND
# ============================================================

def browser_find(pattern: str):
    """
    Find visible elements containing specific text.

    This is important because the LLM should inspect the page
    before trying to click something.
    """

    try:

        page = get_page()

        print()
        print(
            f"[BROWSER] Finding: {pattern}"
        )

        results = []

        # ----------------------------------------------------
        # TEXT MATCH
        # ----------------------------------------------------

        locator = page.get_by_text(
            pattern,
            exact=False
        )

        count = locator.count()

        for index in range(
            min(count, 30)
        ):

            element = locator.nth(index)

            try:

                if not element.is_visible():
                    continue

                text = (
                    element.inner_text(
                        timeout=2000
                    )
                    .strip()
                )

                tag = element.evaluate(
                    "(el) => el.tagName.toLowerCase()"
                )

                html = element.evaluate(
                    "(el) => el.outerHTML.slice(0, 1000)"
                )

                results.append(
                    {
                        "index": index,
                        "tag": tag,
                        "text": text[:500],
                        "html": html,
                    }
                )

            except Exception:
                continue

        # ----------------------------------------------------
        # ARIA / ROLE MATCH
        # ----------------------------------------------------

        if not results:

            for role in [
                "button",
                "link",
                "textbox",
                "combobox",
                "checkbox",
                "radio"
            ]:

                try:

                    role_locator = page.get_by_role(
                        role
                    )

                    role_count = (
                        role_locator.count()
                    )

                    for index in range(
                        min(role_count, 20)
                    ):

                        element = (
                            role_locator.nth(index)
                        )

                        try:

                            if not element.is_visible():
                                continue

                            text = (
                                element.inner_text(
                                    timeout=1000
                                )
                                .strip()
                            )

                            aria = (
                                element.get_attribute(
                                    "aria-label"
                                )
                            )

                            if (
                                pattern.lower()
                                in (
                                    text or ""
                                ).lower()
                                or
                                pattern.lower()
                                in (
                                    aria or ""
                                ).lower()
                            ):

                                results.append(
                                    {
                                        "index": index,
                                        "role": role,
                                        "text": text[:500],
                                        "aria_label": aria,
                                        "html": element.evaluate(
                                            "(el) => el.outerHTML.slice(0, 1000)"
                                        ),
                                    }
                                )

                        except Exception:
                            continue

                except Exception:
                    continue

        result = {
            "success": True,
            "url": page.url,
            "pattern": pattern,
            "matches": results[:30],
            "count": len(results),
        }

        print(
            f"[BROWSER RESULT] Found {len(results)} matches"
        )

        return result

    except Exception as e:

        error = str(e)

        print(
            f"[BROWSER ERROR] {error}"
        )

        return {
            "success": False,
            "error": error,
        }


# ============================================================
# BROWSER TOOL: CLICK
# ============================================================

def browser_click(selector: str):
    """
    Click a specific visible element.

    The agent should preferably use a specific selector
    discovered with browser_find.
    """

    try:

        page = get_page()

        print()
        print(
            f"[BROWSER] Clicking: {selector}"
        )

        locator = page.locator(
            selector
        )

        count = locator.count()

        if count == 0:

            return {
                "success": False,
                "error": (
                    f"No element found for selector: "
                    f"{selector}"
                ),
                "url": page.url,
            }

        # ----------------------------------------------------
        # Find a visible matching element.
        # ----------------------------------------------------

        visible_element = None

        for index in range(
            min(count, 20)
        ):

            candidate = locator.nth(index)

            try:

                if candidate.is_visible():
                    visible_element = candidate
                    break

            except Exception:
                continue

        if visible_element is None:

            return {
                "success": False,
                "error": (
                    f"Elements matched '{selector}', "
                    "but none are visible."
                ),
                "url": page.url,
            }

        # ----------------------------------------------------
        # Click.
        # ----------------------------------------------------

        visible_element.click(
            timeout=8000
        )

        time.sleep(0.5)

        try:
            page.wait_for_load_state(
                "domcontentloaded",
                timeout=3000
            )
        except Exception:
            pass

        result = {
            "success": True,
            "url": page.url,
            "title": page.title(),
        }

        print(
            f"[BROWSER RESULT] {result}"
        )

        return result

    except Exception as e:

        error = str(e)

        print(
            f"[BROWSER ERROR] {error}"
        )

        return {
            "success": False,
            "error": error,
            "url": get_page().url,
        }


# ============================================================
# BROWSER TOOL: TYPE
# ============================================================

def browser_type(
    selector: str,
    text: str
):
    """
    Type text into a specific input.
    """

    try:

        page = get_page()

        print()
        print(
            f"[BROWSER] Typing into: {selector}"
        )

        locator = page.locator(
            selector
        )

        count = locator.count()

        if count == 0:

            return {
                "success": False,
                "error": (
                    f"No element found for selector: "
                    f"{selector}"
                ),
            }

        visible_element = None

        for index in range(
            min(count, 20)
        ):

            candidate = locator.nth(index)

            try:

                if candidate.is_visible():
                    visible_element = candidate
                    break

            except Exception:
                continue

        if visible_element is None:

            return {
                "success": False,
                "error": (
                    f"No visible element found for: "
                    f"{selector}"
                ),
            }

        visible_element.fill(
            text,
            timeout=8000
        )

        result = {
            "success": True,
            "url": page.url,
            "selector": selector,
        }

        print(
            f"[BROWSER RESULT] {result}"
        )

        return result

    except Exception as e:

        error = str(e)

        print(
            f"[BROWSER ERROR] {error}"
        )

        return {
            "success": False,
            "error": error,
        }


# ============================================================
# BROWSER TOOL: PRESS
# ============================================================

def browser_press(
    selector: str,
    key: str
):
    """
    Press a keyboard key on a specific element.
    """

    try:

        page = get_page()

        print()
        print(
            f"[BROWSER] Pressing {key} on {selector}"
        )

        locator = page.locator(
            selector
        )

        count = locator.count()

        if count == 0:

            return {
                "success": False,
                "error": (
                    f"No element found for selector: "
                    f"{selector}"
                ),
            }

        visible_element = None

        for index in range(
            min(count, 20)
        ):

            candidate = locator.nth(index)

            try:

                if candidate.is_visible():
                    visible_element = candidate
                    break

            except Exception:
                continue

        if visible_element is None:

            return {
                "success": False,
                "error": (
                    f"No visible element found for: "
                    f"{selector}"
                ),
            }

        visible_element.press(
            key,
            timeout=8000
        )

        time.sleep(0.5)

        result = {
            "success": True,
            "url": page.url,
            "title": page.title(),
        }

        print(
            f"[BROWSER RESULT] {result}"
        )

        return result

    except Exception as e:

        error = str(e)

        print(
            f"[BROWSER ERROR] {error}"
        )

        return {
            "success": False,
            "error": error,
        }


# ============================================================
# BROWSER TOOL: BACK
# ============================================================

def browser_back():
    """
    Go back one page.
    """

    try:

        page = get_page()

        print()
        print("[BROWSER] Going back")

        page.go_back(
            wait_until="domcontentloaded",
            timeout=15000
        )

        result = {
            "success": True,
            "url": page.url,
            "title": page.title(),
        }

        print(
            f"[BROWSER RESULT] {result}"
        )

        return result

    except Exception as e:

        error = str(e)

        print(
            f"[BROWSER ERROR] {error}"
        )

        return {
            "success": False,
            "error": error,
        }


# ============================================================
# BROWSER TOOL: SCREENSHOT
# ============================================================

def browser_screenshot():
    """
    Take a screenshot of the current page.

    Useful for debugging browser automation.
    """

    try:

        page = get_page()

        timestamp = int(
            time.time()
        )

        screenshot_dir = os.path.expanduser(
            "~/personal-agent-screenshots"
        )

        os.makedirs(
            screenshot_dir,
            exist_ok=True
        )

        path = os.path.join(
            screenshot_dir,
            f"screenshot-{timestamp}.png"
        )

        page.screenshot(
            path=path,
            full_page=True
        )

        result = {
            "success": True,
            "path": path,
            "url": page.url,
            "title": page.title(),
        }

        print(
            f"[BROWSER RESULT] {result}"
        )

        return result

    except Exception as e:

        error = str(e)

        print(
            f"[BROWSER ERROR] {error}"
        )

        return {
            "success": False,
            "error": error,
        }


# ============================================================
# HUMAN APPROVAL
# ============================================================

def request_approval(
    action: str,
    description: str
):
    """
    Ask the application/user for approval before a
    sensitive action.

    This function does NOT perform the action.
    """

    global pending_action

    pending_action = {
        "action": action,
        "description": description,
        "created_at": time.time(),
    }

    print()
    print("=" * 70)
    print("HUMAN APPROVAL REQUIRED")
    print("=" * 70)
    print(
        f"Action: {action}"
    )
    print(
        f"Description: {description}"
    )
    print("=" * 70)

    return {
        "success": False,
        "approval_required": True,
        "action": action,
        "description": description,
        "message": (
            "Human approval is required before "
            "this action can be performed."
        ),
    }


# ============================================================
# TOOL DEFINITIONS FOR GROQ
# ============================================================

TOOLS = [

    # --------------------------------------------------------
    # BROWSER OPEN
    # --------------------------------------------------------

    {
        "type": "function",
        "function": {
            "name": "browser_open",
            "description": (
                "Open a website URL in the headless browser. "
                "Use this when the user asks you to visit a website."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": (
                            "Complete URL including https://"
                        )
                    }
                },
                "required": ["url"]
            }
        }
    },

    # --------------------------------------------------------
    # BROWSER READ
    # --------------------------------------------------------

    {
        "type": "function",
        "function": {
            "name": "browser_read",
            "description": (
                "Read the visible text content of the "
                "currently open webpage."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },

    # --------------------------------------------------------
    # BROWSER FIND
    # --------------------------------------------------------

    {
        "type": "function",
        "function": {
            "name": "browser_find",
            "description": (
                "Find visible webpage elements containing "
                "specific text. Use this BEFORE clicking or "
                "typing when the exact selector is unknown. "
                "Returns matching elements, text, HTML and "
                "ARIA information."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": (
                            "Text to search for on the current webpage."
                        )
                    }
                },
                "required": ["pattern"]
            }
        }
    },

    # --------------------------------------------------------
    # BROWSER CLICK
    # --------------------------------------------------------

    {
        "type": "function",
        "function": {
            "name": "browser_click",
            "description": (
                "Click a specific visible webpage element "
                "using a CSS selector. Do not use generic "
                "selectors such as 'button' when multiple "
                "elements may exist. Use browser_find first "
                "to identify the correct element."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {
                        "type": "string",
                        "description": (
                            "Specific CSS selector for the element."
                        )
                    }
                },
                "required": ["selector"]
            }
        }
    },

    # --------------------------------------------------------
    # BROWSER TYPE
    # --------------------------------------------------------

    {
        "type": "function",
        "function": {
            "name": "browser_type",
            "description": (
                "Enter text into a visible webpage input "
                "using a CSS selector."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {
                        "type": "string",
                        "description": (
                            "Specific CSS selector for the input."
                        )
                    },
                    "text": {
                        "type": "string",
                        "description": (
                            "Text to enter."
                        )
                    }
                },
                "required": [
                    "selector",
                    "text"
                ]
            }
        }
    },

    # --------------------------------------------------------
    # BROWSER PRESS
    # --------------------------------------------------------

    {
        "type": "function",
        "function": {
            "name": "browser_press",
            "description": (
                "Press a keyboard key on a visible webpage "
                "element. Example: Enter."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {
                        "type": "string",
                        "description": (
                            "CSS selector for the target element."
                        )
                    },
                    "key": {
                        "type": "string",
                        "description": (
                            "Keyboard key such as Enter, Tab, "
                            "Escape, ArrowDown."
                        )
                    }
                },
                "required": [
                    "selector",
                    "key"
                ]
            }
        }
    },

    # --------------------------------------------------------
    # BROWSER BACK
    # --------------------------------------------------------

    {
        "type": "function",
        "function": {
            "name": "browser_back",
            "description": (
                "Navigate back to the previous webpage."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },

    # --------------------------------------------------------
    # BROWSER SCREENSHOT
    # --------------------------------------------------------

    {
        "type": "function",
        "function": {
            "name": "browser_screenshot",
            "description": (
                "Take a screenshot of the current webpage "
                "for debugging browser automation."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },

    # --------------------------------------------------------
    # HUMAN APPROVAL
    # --------------------------------------------------------

    {
        "type": "function",
        "function": {
            "name": "request_approval",
            "description": (
                "Request human approval before performing "
                "a sensitive, financial, destructive or "
                "irreversible action."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": (
                            "Short name of the requested action."
                        )
                    },
                    "description": {
                        "type": "string",
                        "description": (
                            "Detailed explanation of what "
                            "will happen."
                        )
                    }
                },
                "required": [
                    "action",
                    "description"
                ]
            }
        }
    },
]


# ============================================================
# TOOL FUNCTION MAP
# ============================================================

TOOL_FUNCTIONS = {

    "browser_open":
        browser_open,

    "browser_read":
        browser_read,

    "browser_find":
        browser_find,

    "browser_click":
        browser_click,

    "browser_type":
        browser_type,

    "browser_press":
        browser_press,

    "browser_back":
        browser_back,

    "browser_screenshot":
        browser_screenshot,

    "request_approval":
        request_approval,
}


# ============================================================
# SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """
You are a personal AI assistant running on a GCP Ubuntu VM.

You have access to a real headless Chromium browser through
Playwright.

You can browse websites and interact with webpages.

============================================================
BROWSER CAPABILITIES
============================================================

Available browser tools:

- browser_open
- browser_read
- browser_find
- browser_click
- browser_type
- browser_press
- browser_back
- browser_screenshot

============================================================
BROWSER WORKFLOW
============================================================

When the user asks you to interact with a website:

1. OPEN the website.
2. READ the page.
3. FIND the desired element if necessary.
4. CLICK or TYPE using a specific selector.
5. READ the resulting page again.
6. Continue until the requested task is complete.

Do not assume that a webpage contains something.

Use browser_read or browser_find to inspect the actual page.

Never invent webpage content, prices, availability,
search results, train information, flight information,
product information or account information.

============================================================
IMPORTANT SELECTOR RULES
============================================================

Never blindly use generic selectors such as:

button
input
a
div

when there may be multiple matching elements.

For example, DO NOT immediately do:

browser_click("button")

Instead:

1. browser_read
2. browser_find("Sign in")
3. inspect the returned HTML/ARIA information
4. use a specific selector

Prefer selectors such as:

#search
input[name="q"]
input[aria-label="Search"]
button[aria-label="Search"]
a[href="..."]

Use browser_find whenever the correct element is not obvious.

============================================================
ERROR HANDLING
============================================================

If a browser action fails:

1. Read the page again.
2. Find the element again.
3. Use a more specific selector.
4. Retry only when there is a reasonable new selector.

Do not repeatedly call the same failed tool with the
same selector.

If a tool reports that an element is hidden, do not
continue clicking that hidden element.

============================================================
SENSITIVE ACTIONS
============================================================

You may browse and research freely.

However, you must request human approval before:

- purchasing something
- placing an order
- making a payment
- booking a railway ticket
- booking a flight
- booking a hotel
- sending an email
- sending a message
- deleting data
- cancelling something
- submitting an irreversible form
- changing important account settings
- any other irreversible or financially significant action

Use request_approval before such actions.

Do not enter passwords into webpages.

Do not ask the user to give you their password.

============================================================
RAILWAY / TRAVEL
============================================================

You may:

- search trains
- inspect schedules
- inspect availability
- compare options
- navigate through booking pages

But before final booking, payment or ticket purchase,
request human approval.

============================================================
EMAIL
============================================================

You may eventually work with email through an authenticated
connector or browser session.

Reading/searching email can be performed when available.

Sending an email requires human approval.

Never ask the user for their email password.

============================================================
LOGIN
============================================================

The browser uses a persistent Chromium profile.

The user may manually authenticate in the browser environment.

Never request passwords through chat.

Do not claim that the user is logged in unless the webpage
actually shows evidence of an authenticated session.

============================================================
CURRENT PAGE
============================================================

Remember that browser state persists during the agent session.

If the user says:

"read it"

"what does it say?"

"continue"

"click that"

"search this"

use the current browser page and conversation context.

============================================================
TRUTHFULNESS
============================================================

Always distinguish between:

- information actually returned by browser tools
- information provided by the user
- your own reasoning

Never fabricate browser results.

============================================================
GENERAL BEHAVIOR
============================================================

You are an action-oriented personal assistant.

Use tools when tools are required.

Do not tell the user that you cannot access websites
when browser tools are available.

Do not merely explain how the user could browse a website
when the user explicitly asked you to browse it.

Actually use the browser tools.

When the task is complete, provide a concise answer.
"""


# ============================================================
# CONVERSATION CLEANING
# ============================================================

def clean_conversation_history(
    conversation_history
):
    """
    Keep only recent user/assistant messages.
    """

    if not conversation_history:
        return []

    cleaned = []

    recent = conversation_history[
        -MAX_SHORT_TERM_MESSAGES:
    ]

    for item in recent:

        if not isinstance(
            item,
            dict
        ):
            continue

        role = item.get(
            "role"
        )

        content = item.get(
            "content",
            ""
        )

        if role not in [
            "user",
            "assistant"
        ]:
            continue

        if not content:
            continue

        if len(content) > 4000:

            content = (
                content[:4000]
                + "\n...[truncated]"
            )

        cleaned.append(
            {
                "role": role,
                "content": content
            }
        )

    return cleaned


# ============================================================
# TOOL ARGUMENT PARSER
# ============================================================

def parse_tool_arguments(
    arguments
):
    """
    Safely parse Groq tool arguments.
    """

    if arguments is None:
        return {}

    if isinstance(
        arguments,
        dict
    ):
        return arguments

    try:
        return json.loads(
            arguments
        )

    except Exception:
        return {}


# ============================================================
# TOOL EXECUTION
# ============================================================

def execute_tool(
    tool_name,
    arguments
):
    """
    Execute one registered tool.
    """

    print()
    print(
        f"[AGENT TOOL] {tool_name}"
    )

    print(
        f"[ARGUMENTS] {arguments}"
    )

    function = TOOL_FUNCTIONS.get(
        tool_name
    )

    if function is None:

        error = (
            f"Tool '{tool_name}' is not registered."
        )

        print(
            f"[TOOL ERROR] {error}"
        )

        return {
            "success": False,
            "error": error,
            "available_tools": list(
                TOOL_FUNCTIONS.keys()
            ),
        }

    try:

        result = function(
            **arguments
        )

        print(
            f"[TOOL RESULT] {result}"
        )

        return result

    except Exception as e:

        error = str(e)

        print(
            f"[TOOL ERROR] {error}"
        )

        traceback.print_exc()

        return {
            "success": False,
            "error": error,
        }


# ============================================================
# MAIN AGENT
# ============================================================

def run_agent(
    task,
    conversation_history=None,
    conversation_id=None,
    **kwargs
):
    """
    Main personal AI agent.

    Compatible with the Flask application:

        result = run_agent(
            task=prompt,
            conversation_history=history,
            conversation_id=session_id
        )
    """

    print()
    print("=" * 70)
    print("CHAT REQUEST")
    print(
        f"Conversation: {conversation_id}"
    )
    print(
        f"Previous messages: "
        f"{len(conversation_history or [])}"
    )
    print(
        f"User: {task}"
    )
    print("=" * 70)

    # --------------------------------------------------------
    # BUILD MESSAGES
    # --------------------------------------------------------

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        }
    ]

    # --------------------------------------------------------
    # PREVIOUS CONVERSATION
    # --------------------------------------------------------

    history = clean_conversation_history(
        conversation_history
    )

    messages.extend(
        history
    )

    # --------------------------------------------------------
    # CURRENT USER REQUEST
    # --------------------------------------------------------

    messages.append(
        {
            "role": "user",
            "content": task
        }
    )

    # --------------------------------------------------------
    # TOOL LOOP
    # --------------------------------------------------------

    for iteration in range(
        1,
        MAX_TOOL_ITERATIONS + 1
    ):

        print()
        print("=" * 70)
        print(
            f"AGENT ITERATION: {iteration}"
        )
        print("=" * 70)

        # ----------------------------------------------------
        # CALL GROQ
        # ----------------------------------------------------

        try:

            response = (
                client
                .chat
                .completions
                .create(
                    model=MODEL,
                    messages=messages,
                    tools=TOOLS,
                    tool_choice="auto",
                    temperature=0.2,
                    max_completion_tokens=2048,
                    reasoning_effort="medium",
                )
            )

        except Exception as e:

            error = str(e)

            print(
                f"CHAT ERROR: {error}"
            )

            return {
                "response": (
                    "The AI model encountered an error "
                    "while processing the request."
                ),
                "error": error,
                "conversation_id": conversation_id,
            }

        # ----------------------------------------------------
        # GET MESSAGE
        # ----------------------------------------------------

        message = (
            response
            .choices[0]
            .message
        )

        # ----------------------------------------------------
        # NO TOOL CALL
        # ----------------------------------------------------

        if not message.tool_calls:

            answer = (
                message.content
                or
                "I completed the request."
            )

            print()
            print(
                "[AGENT FINAL RESPONSE]"
            )
            print(
                answer
            )

            return {
                "response": answer,
                "conversation_id": conversation_id,
            }

        # ----------------------------------------------------
        # APPEND ASSISTANT TOOL CALL MESSAGE
        # ----------------------------------------------------

        assistant_message = {
            "role": "assistant",
            "content": (
                message.content
                or ""
            ),
            "tool_calls": []
        }

        for tool_call in (
            message.tool_calls
        ):

            assistant_message[
                "tool_calls"
            ].append(
                {
                    "id": tool_call.id,
                    "type": "function",
                    "function": {
                        "name":
                            tool_call.function.name,
                        "arguments":
                            tool_call.function.arguments,
                    },
                }
            )

        messages.append(
            assistant_message
        )

        # ----------------------------------------------------
        # EXECUTE TOOL CALLS
        # ----------------------------------------------------

        for tool_call in (
            message.tool_calls
        ):

            tool_name = (
                tool_call
                .function
                .name
            )

            raw_arguments = (
                tool_call
                .function
                .arguments
            )

            arguments = parse_tool_arguments(
                raw_arguments
            )

            # ------------------------------------------------
            # SAFETY CHECK
            # ------------------------------------------------

            if tool_name not in TOOL_FUNCTIONS:

                tool_result = {
                    "success": False,
                    "error": (
                        f"Tool '{tool_name}' is not "
                        "registered."
                    ),
                    "available_tools": list(
                        TOOL_FUNCTIONS.keys()
                    ),
                }

            else:

                tool_result = execute_tool(
                    tool_name,
                    arguments
                )

            # ------------------------------------------------
            # PENDING APPROVAL
            # ------------------------------------------------

            if (
                isinstance(
                    tool_result,
                    dict
                )
                and
                tool_result.get(
                    "approval_required"
                )
            ):

                return {
                    "response": (
                        "This action requires your approval "
                        "before I can continue."
                    ),
                    "pending_action":
                        tool_result,
                    "conversation_id":
                        conversation_id,
                }

            # ------------------------------------------------
            # SERIALIZE TOOL RESULT
            # ------------------------------------------------

            try:

                tool_content = json.dumps(
                    tool_result,
                    ensure_ascii=False
                )

            except Exception:

                tool_content = str(
                    tool_result
                )

            # ------------------------------------------------
            # APPEND TOOL RESULT
            # ------------------------------------------------

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id":
                        tool_call.id,
                    "content":
                        tool_content,
                }
            )

    # ========================================================
    # MAX ITERATIONS
    # ========================================================

    print()
    print(
        "[AGENT] Maximum tool iterations reached."
    )

    return {
        "response": (
            "I reached the maximum number of browser "
            "actions for this request. The task may "
            "require another step."
        ),
        "conversation_id": conversation_id,
        "error": "max_tool_iterations",
    }


# ============================================================
# SHUTDOWN
# ============================================================

def shutdown_browser():
    """
    Cleanly close Chromium.
    """

    global browser_context
    global playwright_instance

    try:

        if browser_context is not None:

            browser_context.close()

            browser_context = None

    except Exception:
        pass

    try:

        if playwright_instance is not None:

            playwright_instance.stop()

            playwright_instance = None

    except Exception:
        pass


atexit.register(
    shutdown_browser
)


# ============================================================
# DIRECT TEST
# ============================================================

if __name__ == "__main__":

    print()
    print("=" * 70)
    print("PERSONAL AI AGENT")
    print("=" * 70)

    print(
        "Browser profile:"
    )

    print(
        BROWSER_DATA_DIR
    )

    print()
    print(
        "Type 'exit' to quit."
    )

    print()

    while True:

        try:

            user_input = input(
                "You: "
            ).strip()

        except (
            KeyboardInterrupt,
            EOFError
        ):

            print()
            break

        if not user_input:
            continue

        if user_input.lower() in [
            "exit",
            "quit"
        ]:
            break

        result = run_agent(
            task=user_input,
            conversation_history=[]
        )

        print()
        print(
            "Agent:",
            result.get(
                "response",
                ""
            )
        )

        if result.get(
            "pending_action"
        ):

            print()
            print(
                "PENDING ACTION:"
            )

            print(
                json.dumps(
                    result[
                        "pending_action"
                    ],
                    indent=2
                )
            )

        print()
