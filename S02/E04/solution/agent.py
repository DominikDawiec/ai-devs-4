import os
import json
import requests
from openai import OpenAI
from dotenv import load_dotenv

# Load API keys from root .env file
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
AI_DEVS_KEY = os.environ["AI_DEVS_API_KEY"]

ZMAIL_URL = "https://hub.ag3nts.org/api/zmail"   # mailbox API
VERIFY_URL = "https://hub.ag3nts.org/verify"      # answer submission endpoint


# ── API WRAPPERS ──────────────────────────────────────────────────────────────
# Each function calls the zmail API with a specific action.
# The agent calls these as tools during the reasoning loop.

def search_mail(query: str, page: int = 1) -> dict:
    """Search emails using Gmail-style operators: from:, to:, subject:, OR, AND."""
    resp = requests.post(ZMAIL_URL, json={
        "apikey": AI_DEVS_KEY,
        "action": "search",
        "query": query,
        "page": page,
    })
    return resp.json()


def get_mail(mail_id: str) -> dict:
    """Fetch the full body of a single email by its messageID."""
    resp = requests.post(ZMAIL_URL, json={
        "apikey": AI_DEVS_KEY,
        "action": "getMessages",
        "ids": mail_id,
    })
    return resp.json()


def get_inbox(page: int = 1) -> dict:
    """List inbox emails paginated (newest first). Use when search doesn't find anything."""
    resp = requests.post(ZMAIL_URL, json={
        "apikey": AI_DEVS_KEY,
        "action": "getInbox",
        "page": page,
    })
    return resp.json()


def submit_answer(date: str, password: str, confirmation_code: str) -> dict:
    """Send the three collected values to the verification hub.
    Returns a flag {FLG:...} if all values are correct, or an error message otherwise."""
    payload = {
        "apikey": AI_DEVS_KEY,
        "task": "mailbox",
        "answer": {
            "date": date,
            "password": password,
            "confirmation_code": confirmation_code,
        },
    }
    resp = requests.post(VERIFY_URL, json=payload)
    print(f"  ↳ HTTP {resp.status_code}: {resp.text[:400]}")
    try:
        return resp.json()
    except Exception:
        return {"raw": resp.text}


# ── TOOL DISPATCHER ───────────────────────────────────────────────────────────
# Receives a tool call from the model, routes it to the right function,
# prints what happened, and returns the result as a JSON string for the model.

def handle_tool_call(name: str, args: dict) -> str:
    print(f"\n  🔧 {name}({args})")
    if name == "search_mail":
        result = search_mail(**args)
    elif name == "get_mail":
        result = get_mail(**args)
    elif name == "get_inbox":
        result = get_inbox(**args)
    elif name == "submit_answer":
        result = submit_answer(**args)
    else:
        result = {"error": f"Unknown tool: {name}"}
    print(f"  📨 {json.dumps(result, ensure_ascii=False)[:300]}")
    return json.dumps(result)


# ── TOOL SCHEMAS ──────────────────────────────────────────────────────────────
# Describes each tool to the model so it knows what's available and how to call it.

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_mail",
            "description": (
                "Search the mailbox using Gmail-style operators: from:, to:, subject:, OR, AND. "
                "Returns a list of emails with metadata (no body). "
                "Example query: 'from:proton.me'"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query with Gmail operators"},
                    "page": {"type": "integer", "description": "Page number, default 1"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_mail",
            "description": "Fetch the full body of an email by its ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "mail_id": {"type": "string", "description": "Email ID from search results"},
                },
                "required": ["mail_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_inbox",
            "description": "Get the latest emails from the inbox (paginated, newest first).",
            "parameters": {
                "type": "object",
                "properties": {
                    "page": {"type": "integer", "description": "Page number, default 1"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "submit_answer",
            "description": (
                "Submit the three collected values to the verification endpoint. "
                "The hub will return a flag if all values are correct, "
                "or an error if any value is wrong. "
                "Call this once you have candidates for all three fields."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "Date of planned attack, format YYYY-MM-DD",
                    },
                    "password": {
                        "type": "string",
                        "description": "Employee system password found in the mailbox",
                    },
                    "confirmation_code": {
                        "type": "string",
                        "description": "Ticket confirmation code, format SEC- followed by exactly 32 hex chars (36 total)",
                    },
                },
                "required": ["date", "password", "confirmation_code"],
            },
        },
    },
]


# ── SYSTEM PROMPT ─────────────────────────────────────────────────────────────
# Tells the model what its goal is, what facts it knows, and how to approach the task.

SYSTEM_PROMPT = """You are an intelligence agent tasked with extracting three pieces of information
from a live email inbox via API. The mailbox is in Polish.

Your goal is to find:
1. date - when the security department plans to attack our power plant (format YYYY-MM-DD)
2. password - an employee system password that is somewhere in the mailbox
3. confirmation_code - a security ticket confirmation code (format: SEC- + 32 hex chars = 36 total)

Key facts:
- Wiktor (the informant who betrayed us) sent an email from a @proton.me address
- The mailbox is active — new emails may arrive during your search
- All emails are in Polish — search using Polish keywords
- Always fetch the full mail body after finding a match — never guess from subject alone
- The inbox has many pages — scan ALL pages if search fails

Strategy:
1. search from:proton.me → find Wiktor's email and read its thread for the attack date
2. Search Polish keywords for password: "hasło", "nowe hasło", "system pracowniczy"
3. Search "SEC-" for the confirmation code
4. If search fails, use get_inbox and iterate through ALL pages reading subjects
5. Once you have all three values, call submit_answer — it returns hub feedback on wrong values
6. Keep searching until you receive a flag {FLG:...} in the response

Important:
- Never give up — if search finds nothing, browse inbox page by page (there are up to 15 pages)
- Before submitting, count the confirmation_code chars: SEC- (4) + exactly 32 hex chars = 36 total
- If submit returns an error, re-read the source email and double-check each character
"""


# ── AGENT LOOP ────────────────────────────────────────────────────────────────
# The core ReAct loop: ask the model → execute tools → feed results back → repeat.
# Stops when the model finds the flag or hits the step limit.

def run_agent():
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "Start searching the mailbox and find all three values. Go."},
    ]

    print("=" * 60)
    print("  MAILBOX AGENT STARTING")
    print("=" * 60)

    for step in range(1, 31):  # safety limit of 30 steps
        print(f"\n{'─' * 60}")
        print(f"  STEP {step}")
        print(f"{'─' * 60}")

        response = client.chat.completions.create(
            model="gpt-4o",
            tools=TOOLS,
            messages=messages,
            tool_choice="auto",
        )

        msg = response.choices[0].message
        messages.append(msg)

        # If the model didn't call any tools, it got stuck — push it to keep going
        if not msg.tool_calls:
            print(f"\n  💭 Agent thinking: {msg.content}")
            messages.append({
                "role": "user",
                "content": (
                    "Don't stop. Keep searching and trying. "
                    "If you got an error from submit_answer, re-read the emails and verify each value carefully — "
                    "especially the confirmation_code (must be exactly SEC- + 32 hex chars = 36 chars total). "
                    "Try different search terms or browse inbox pages. Never give up until you see {FLG:...} in a response."
                ),
            })
            continue

        # Execute every tool the model requested in this step
        for tool_call in msg.tool_calls:
            name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)
            result = handle_tool_call(name, args)

            # Feed the tool result back into the conversation
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result,
            })

            # Check if the hub returned a flag — if so, we're done
            try:
                data = json.loads(result)
                if isinstance(data, dict):
                    for v in data.values():
                        if isinstance(v, str) and v.startswith("{FLG:"):
                            print(f"\n{'=' * 60}")
                            print(f"  🏁 FLAG FOUND: {v}")
                            print(f"{'=' * 60}")
                            return
            except Exception:
                pass

    print("\n⚠️  Step limit reached without finding the flag.")


if __name__ == "__main__":
    run_agent()
