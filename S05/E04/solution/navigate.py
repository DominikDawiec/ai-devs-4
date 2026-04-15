#!/usr/bin/env python3
"""S05E04 goingthere - rocket navigation with radar disarming."""
import anthropic
import requests
import hashlib
import time
import re
import os
from dotenv import load_dotenv

load_dotenv('/Users/dominikdawiec/AI_Devs_4/.env')

VERIFY_URL = "https://hub.ag3nts.org/verify"
GETMESSAGE_URL = "https://hub.ag3nts.org/api/getmessage"
SCANNER_URL = "https://hub.ag3nts.org/api/frequencyScanner"
API_KEY = os.environ.get('AI_DEVS_API_KEY', '8573e442-91ca-44af-b520-35e0f6b26bc6')

client = anthropic.Anthropic()

def sha1(text):
    return hashlib.sha1(text.encode()).hexdigest()

def post_verify(payload):
    r = requests.post(VERIFY_URL, json=payload, headers={'Content-Type': 'application/json'}, timeout=15)
    return r.json()

def get_hint():
    """Get navigation hint with retry on rate limit."""
    for attempt in range(5):
        try:
            r = requests.post(GETMESSAGE_URL, json={"apikey": API_KEY},
                              headers={'Content-Type': 'application/json'}, timeout=15)
            data = r.json()
            hint = ''
            if isinstance(data, dict):
                hint = data.get('hint', data.get('message', str(data)))
            else:
                hint = str(data)
            # Check for rate limit
            if 'często' in hint or 'zwolnij' in hint.lower() or 'slow down' in hint.lower():
                print(f"  RATE LIMIT: waiting 3s... ({hint[:50]})")
                time.sleep(3)
                continue
            return hint
        except Exception as e:
            time.sleep(2)
    return None

def scan_text():
    r = requests.get(f"{SCANNER_URL}?key={API_KEY}", timeout=10)
    return r.text

def disarm_radar(freq, hash_val):
    r = requests.post(SCANNER_URL, json={"apikey": API_KEY, "frequency": freq, "disarmHash": hash_val},
                      headers={'Content-Type': 'application/json'}, timeout=10)
    return r.json()

def is_clear_text(text):
    """Check if scanner says 'clear' in any garbled form."""
    if len(text) > 300:
        return False
    if text.strip().startswith('<') or 'DOCTYPE' in text:
        return False
    return bool(re.search(r"it.{0,6}s\s*cl|clear", text, re.IGNORECASE))

def parse_radar_response(text):
    """Use Claude to extract frequency + detectionCode from garbled JSON."""
    r = client.messages.create(
        model='claude-haiku-4-5-20251001',
        max_tokens=80,
        messages=[{'role': 'user', 'content':
            f'Extract frequency number and detectionCode string from this text. '
            f'Reply: FREQ=<number> CODE=<string>\nIf it says clear: reply CLEAR\n\n{text[:400]}'}]
    )
    resp = r.content[0].text.strip()
    if 'CLEAR' in resp.upper():
        return 'clear'
    fm = re.search(r'FREQ[=:]\s*([\d.]+)', resp, re.IGNORECASE)
    cm = re.search(r'CODE[=:]\s*(\S+)', resp, re.IGNORECASE)
    if fm and cm:
        try:
            return {'frequency': int(float(fm.group(1))), 'code': cm.group(1)}
        except ValueError:
            return None
    return None

def handle_scanner(player_row, player_col):
    """Poll scanner until clear, disarming radars as needed."""
    for _ in range(30):
        try:
            text = scan_text()
        except Exception:
            time.sleep(0.5)
            continue

        if not text or not text.strip():
            time.sleep(0.3)
            continue
        if text.strip().startswith('<') or 'DOCTYPE' in text.lower():
            time.sleep(0.3)
            continue

        if is_clear_text(text):
            print(f"  CLEAR: {text.strip()[:70]}")
            return

        result = parse_radar_response(text)
        if result == 'clear':
            print("  CLEAR (parsed)")
            return
        if result and 'frequency' in result:
            freq = result['frequency']
            code = result['code']
            h = sha1(code + 'disarm')
            print(f"  RADAR: freq={freq} code={code}")
            dr = disarm_radar(freq, h)
            print(f"  DISARMED: {str(dr)[:80]}")
            time.sleep(0.5)
            continue

        print(f"  SCANNER?: {text.strip()[:80]}")
        time.sleep(0.3)

    print("  WARNING: Scanner not clear after 30 attempts, proceeding")

def get_stone_row(hint_text, player_row):
    """Parse hint to determine which row has the stone in the NEXT column.

    Key insight: hints use RELATIVE language.
    - "port" / "left side" = Row 1 (absolute)
    - "starboard" / "right side" = Row 3 (absolute)
    - "center" / "middle" / "ahead" / "in front" / "bow" = same row as player (relative)

    Returns: 1, 2, or 3
    """
    prompt = f"""Rocket navigation hint analysis. Grid has 3 rows:
- Row 1 = PORT side (left, top)
- Row 2 = CENTER (middle)
- Row 3 = STARBOARD side (right, bottom)

Rocket is currently at Row {player_row}.

IMPORTANT RULES for interpreting hints:
- "port" / "port side" / "left side" = Row 1 (absolute)
- "starboard" / "starboard side" / "right side" = Row 3 (absolute)
- "center lane" / "middle" / "ahead" / "in front" / "bow" / "nose" / "straight" / "directly in front" = Row {player_row} (SAME AS ROCKET = relative/ahead)
- "both edges" / "both sides" = the rows that are NOT the player's row

Hint: "{hint_text}"

Where is the STONE/ROCK/OBSTACLE/BLOCKAGE in the next column?
Reply with ONLY one number: 1, 2, or 3"""

    r = client.messages.create(
        model='claude-opus-4-6',
        max_tokens=10,
        messages=[{'role': 'user', 'content': prompt}]
    )
    resp = r.content[0].text.strip()
    for ch in resp:
        if ch in '123':
            return int(ch)
    return player_row  # default: stone ahead (safest assumption)

def choose_command(player_row, stone_row, base_row):
    """Determine best move: go / left / right.

    left = row-1 (toward port/row1)
    right = row+1 (toward starboard/row3)
    go = stay in same row

    When stone is at player's row (must dodge): always prefer going to row=3 (starboard)
    to avoid common crash pattern where going to row=1 hits unexpected stones.
    """
    if stone_row == player_row:
        # MUST leave current row
        if player_row == 1:
            return 'right'   # only option
        elif player_row == 3:
            return 'left'    # only option
        else:  # player at row=2
            # ALWAYS go right (to row=3) regardless of base.
            # Reason: going left (to row=1) crashes too often due to wrong hints.
            # Row=3 is consistently safer when stone is "ahead" for player at row=2.
            return 'right'
    else:
        # Safe to stay OR move toward base
        if player_row == base_row:
            return 'go'  # already aligned, stay
        elif player_row < base_row:
            # Need to go right (increase row toward starboard/base)
            new_row = player_row + 1
            return 'right' if new_row != stone_row else 'go'
        else:
            # Need to go left (decrease row toward port/base)
            new_row = player_row - 1
            return 'left' if new_row != stone_row else 'go'

def run_attempt(attempt_num):
    print(f"\n{'='*50}")
    print(f"ATTEMPT {attempt_num}")

    start = post_verify({"apikey": API_KEY, "task": "goingthere", "answer": {"command": "start"}})
    if 'player' not in start:
        print(f"Start failed: {start}")
        return None

    player_row = start['player']['row']
    player_col = start['player']['col']
    base_row = start.get('base', {}).get('row', 1)
    print(f"Start: row={player_row} col={player_col} → Base row={base_row} col=12")

    for step in range(12):
        print(f"\n[row={player_row} col={player_col}]")

        # 1. Clear scanner
        handle_scanner(player_row, player_col)

        # 2. Get hint for next column (with rate limit handling)
        time.sleep(0.5)  # small delay to avoid rate limits
        hint_text = get_hint()
        if not hint_text:
            print("  WARNING: Could not get hint, using default strategy")
            hint_text = ""
        print(f"Hint: {hint_text[:120]}")

        # 3. Determine stone row in next column
        if hint_text:
            stone_row = get_stone_row(hint_text, player_row)
        else:
            stone_row = player_row  # assume stone ahead = must move
        print(f"Stone in next col: row={stone_row}")

        # 4. Choose command
        cmd = choose_command(player_row, stone_row, base_row)
        print(f"CMD: {cmd}  [player={player_row}, stone={stone_row}, base={base_row}]")

        # 5. Execute move
        result = post_verify({"apikey": API_KEY, "task": "goingthere", "answer": {"command": cmd}})

        result_str = str(result)
        print(f"Result: {result_str[:150]}")

        # Check for flag
        flg = re.search(r'\{FLG:[^}]+\}', result_str)
        if flg:
            print(f"\n*** FLAG: {flg.group(0)} ***")
            return flg.group(0)

        if isinstance(result, dict) and result.get('crashed'):
            print(f"CRASHED! Reason: {result.get('crashReason', '?')}")
            return None

        if isinstance(result, dict) and 'player' in result:
            player_row = result['player']['row']
            player_col = result['player']['col']

            if player_col >= 12:
                print(f"Reached col=12! Result: {result_str}")
                # Send one more go to see if we get a flag
                final = post_verify({"apikey": API_KEY, "task": "goingthere", "answer": {"command": "go"}})
                print(f"Final: {final}")
                flg2 = re.search(r'\{FLG:[^}]+\}', str(final))
                if flg2:
                    return flg2.group(0)
                return result_str
        else:
            print(f"Unexpected: {result_str}")
            return None

    print(f"Completed moves. Last pos: row={player_row} col={player_col}")
    return None

def main():
    flag = None
    for attempt in range(1, 100):
        result = run_attempt(attempt)
        if result:
            if '{FLG:' in str(result):
                flag = result
                print(f"\n=== FINAL FLAG: {flag} ===")
                break
            print(f"Non-flag result: {result}")
        time.sleep(1)

    print(f"\n=== FINAL FLAG: {flag} ===")

if __name__ == '__main__':
    main()
