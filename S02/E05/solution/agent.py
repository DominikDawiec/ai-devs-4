import os
import json
import requests
from langfuse.openai import OpenAI          # drop-in replacement — auto-traces all LLM calls
from langfuse import observe                # wraps functions as named Langfuse spans (v3+)
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
AI_DEVS_KEY = os.environ["AI_DEVS_API_KEY"]

VERIFY_URL = "https://hub.ag3nts.org/verify"
MAP_URL = f"https://hub.ag3nts.org/data/{AI_DEVS_KEY}/drone.png"
MODEL = "gpt-4o"
FLAG_PREFIX = "{FLG:"


# ── FAZA 1: ANALIZA MAPY ──────────────────────────────────────────────────────
# Jednorazowe wywołanie modelu vision — lokalizuje tamę na siatce mapy.
# Wynik (x, y) jest potem wstrzykiwany do systemu promptu agenta.

@observe()  # tworzy span "analyze_map" w Langfuse z inputem/outputem
def analyze_map() -> str:
    print("📸 Analizuję mapę modelem vision...")
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": (
                        "This is a grid map of a power plant area. "
                        "Locate the dam (tama) — it's marked by intensified blue water color. "
                        "Count columns (x) left→right from 1, rows (y) top→bottom from 1. "
                        "Reply with ONLY: x=<number>, y=<number>"
                    ),
                },
                {
                    "type": "image_url",
                    "image_url": {"url": MAP_URL},
                },
            ],
        }],
        max_tokens=30,
    )
    result = response.choices[0].message.content.strip()
    print(f"  📍 Tama: {result}")
    return result


# ── NARZĘDZIE: WYSYŁANIE INSTRUKCJI ──────────────────────────────────────────
# Wysyła tablicę instrukcji do endpointu /verify i zwraca odpowiedź API.
# Kluczowe instrukcje do misji:
#   setDestinationObject(PWR6132PL) — cel zarejestrowany w systemie
#   set(x,y)                        — sektor lądowania (tama)
#   set(Xm)                         — wysokość lotu
#   set(destroy)                    — cel misji: zniszczenie
#   flyToLocation                   — wykonaj lot (wymaga height + object + sector)

def submit_instructions(instructions: list) -> dict:
    resp = requests.post(VERIFY_URL, json={
        "apikey": AI_DEVS_KEY,
        "task": "drone",
        "answer": {"instructions": instructions},
    })
    print(f"  ↳ HTTP {resp.status_code}: {resp.text[:400]}")
    try:
        return resp.json()
    except Exception:
        return {"raw": resp.text}


# ── SCHEMAT NARZĘDZIA DLA MODELU ──────────────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "submit_instructions",
            "description": (
                "Send drone instructions to /verify. "
                "Required before flyToLocation: setDestinationObject(ID), set(x,y), set(Xm). "
                "Use set(destroy) for mission objective. "
                "API returns precise error messages — read and adjust. "
                "Use hardReset if state is corrupted."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "instructions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Ordered list of drone API instruction strings",
                    }
                },
                "required": ["instructions"],
            },
        },
    }
]


# ── FAZA 2: PĘTLA AGENTOWA ────────────────────────────────────────────────────
# Agent dostaje lokalizację tamy i samodzielnie dobiera instrukcje.
# Iteruje na podstawie komunikatów błędów API aż do uzyskania flagi.

@observe()  # tworzy span "run_agent" zagnieżdżony w głównym trace
def run_agent(dam_coords: str):
    messages = [
        {
            "role": "system",
            "content": (
                "You are a drone operator executing a covert mission.\n\n"
                "MISSION BRIEF:\n"
                f"- Register target in system as: PWR6132PL (power plant)\n"
                f"- Actual bomb drop sector (dam location): {dam_coords}\n\n"
                "REQUIRED INSTRUCTION SEQUENCE (send all in one call, flyToLocation MUST be last):\n"
                "  1. setDestinationObject(PWR6132PL)\n"
                "  2. set(x,y)           ← dam sector coordinates\n"
                "  3. set(50m)           ← altitude — MUST include 'm', e.g. set(50m) not set(50)\n"
                "  4. set(engineON)      ← start engines\n"
                "  5. set(100%)          ← engine power, required or drone won't move\n"
                "  6. set(destroy)       ← mission objective\n"
                "  7. set(return)        ← return instruction, required or drone is lost forever\n"
                "  8. flyToLocation      ← ALWAYS LAST, executes the flight\n\n"
                "ERROR GUIDE:\n"
                "- 'won't hit the dam'           → wrong (x,y) sector, try a different one\n"
                "- 'pretending to destroy plant' → that sector IS the power plant, skip it\n"
                "- 'trees at this height'        → sector may be correct, increase altitude\n"
                "- 'engine power 0%'             → add set(100%) before flyToLocation\n"
                "- 'lose it forever'             → add set(return) before flyToLocation\n"
                "- After hardReset ALL settings clear — re-send full sequence\n\n"
                "COORDINATE STRATEGY:\n"
                "Known bad sectors (wrong): (3,3), (3,4), (4,3), (3,2), (4,4), (3,5), (4,5), (4,2), (3,2)\n"
                "Known power plant sectors (skip): (2,3), (2,5)\n"
                "Promising: (2,4) got 'trees' error — try with higher altitude like set(100m)\n"
                "Try in order: (2,4), (1,3), (1,4), (1,2), (2,2), (5,3), (5,4)\n\n"
                "Send the COMPLETE sequence in ONE call. Keep trying until {FLG:...}."
            ),
        },
        {"role": "user", "content": "Execute the mission."},
    ]

    print("\n" + "=" * 60)
    print("  DRONE AGENT STARTING")
    print("=" * 60)

    for step in range(1, 41):
        print(f"\n{'─' * 60}")
        print(f"  STEP {step}")
        print(f"{'─' * 60}")

        msg = client.chat.completions.create(
            model=MODEL,
            tools=TOOLS,
            messages=messages,
        ).choices[0].message
        messages.append(msg)

        # Gdy model nie wywołuje narzędzia — sprawdź czy nie ma flagi w treści
        if not msg.tool_calls:
            print(f"\n  💭 {msg.content}")
            if msg.content and FLAG_PREFIX in msg.content:
                flag = msg.content[msg.content.index(FLAG_PREFIX):]
                flag = flag[:flag.index("}") + 1]
                print(f"\n{'=' * 60}")
                print(f"  🏁 FLAG FOUND: {flag}")
                print(f"{'=' * 60}")
                return
            messages.append({
                "role": "user",
                "content": (
                    "Keep going. If you keep getting -880 error with the same sector coordinates, "
                    "the vision model may have been off by 1-2 cells. "
                    "Try systematically different (x,y) values around your current estimate. "
                    "Don't stop until {FLG:...}."
                ),
            })
            continue

        # Wykonaj wywołanie narzędzia i przekaż wynik z powrotem do modelu
        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments)
            print(f"\n  🚁 submit_instructions({args['instructions']})")
            result = submit_instructions(**args)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result),
            })

            # Sprawdź czy API zwróciło flagę
            flag = next(
                (v for v in result.values() if isinstance(v, str) and v.startswith(FLAG_PREFIX)),
                None,
            )
            if flag:
                print(f"\n{'=' * 60}")
                print(f"  🏁 FLAG FOUND: {flag}")
                print(f"{'=' * 60}")
                return

    print("\n⚠️  Step limit reached.")


# ── MAIN ──────────────────────────────────────────────────────────────────────

@observe()  # główny trace widoczny w Langfuse — opakowuje całą sesję
def main():
    dam_coords = analyze_map()
    run_agent(dam_coords)


if __name__ == "__main__":
    main()
