"""
S03E04 — Tool server for the negotiations agent.
Provides item search with keyword + LLM matching.
"""
import csv
import re
import os
from collections import defaultdict
from flask import Flask, request, jsonify
from anthropic import Anthropic

app = Flask(__name__)

DATA_DIR = os.path.dirname(os.path.abspath(__file__))

# --- Load data ---
items = []
with open(os.path.join(DATA_DIR, "items.csv")) as f:
    items = list(csv.DictReader(f))

item_by_code = {it["code"]: it["name"] for it in items}

city_by_code = {}
with open(os.path.join(DATA_DIR, "cities.csv")) as f:
    city_by_code = {c["code"]: c["name"] for c in csv.DictReader(f)}

item_cities = defaultdict(set)
with open(os.path.join(DATA_DIR, "connections.csv")) as f:
    for row in csv.DictReader(f):
        item_cities[row["itemCode"]].add(row["cityCode"])

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9ąćęłńóśźż\s/.]", "", text.lower())


def keyword_search(query: str, top_n: int = 30) -> list[dict]:
    """Score items by keyword overlap with query."""
    query_norm = normalize(query)
    words = [w for w in query_norm.split() if len(w) > 1]

    scored = []
    for item in items:
        name_norm = normalize(item["name"])
        # Exact substring match scores higher
        score = 0
        for w in words:
            if w in name_norm:
                score += 2 if len(w) > 3 else 1
        if score > 0:
            scored.append((score, item))

    scored.sort(key=lambda x: -x[0])
    return [it for _, it in scored[:top_n]]


def match_with_llm(query: str, candidates: list[dict]) -> list[str]:
    """Use Claude to pick the best item from pre-filtered candidates."""
    if not candidates:
        return []

    catalog = "\n".join(f"{it['code']}|{it['name']}" for it in candidates)
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=100,
        messages=[{
            "role": "user",
            "content": (
                f"Product catalog:\n{catalog}\n\n"
                f"User needs: \"{query}\"\n\n"
                "Return ONLY the single best matching item code. "
                "Match voltage, power, capacity etc. if specified. "
                "One code, nothing else."
            ),
        }],
    )
    code = resp.content[0].text.strip().split("\n")[0].strip()
    if code in item_by_code:
        return [code]
    return []


def find_item(query: str) -> list[str]:
    """Find matching item codes for a query."""
    # 1. Direct code lookup
    query_upper = query.strip().upper()
    for code in item_by_code:
        if code in query_upper:
            return [code]

    # 2. Keyword pre-filter
    candidates = keyword_search(query)

    if not candidates:
        return []

    # 3. If single strong match or few candidates, use top result
    if len(candidates) == 1:
        return [candidates[0]["code"]]

    # 4. Use LLM to disambiguate among candidates
    try:
        codes = match_with_llm(query, candidates[:30])
        if codes:
            return codes
    except Exception as e:
        app.logger.error(f"LLM error: {e}")

    # 5. Fallback: return top keyword match
    return [candidates[0]["code"]]


@app.route("/api/search", methods=["POST"])
def search():
    """Search for items and return cities that sell them."""
    data = request.json or {}
    query = data.get("params", "")
    app.logger.info(f"QUERY: {query}")

    if not query or len(query.strip()) < 2:
        return jsonify({"output": "Provide an item description to search."})

    codes = find_item(query)

    if not codes:
        return jsonify({"output": "No matching items. Try different keywords."})

    parts = []
    for code in codes[:2]:
        name = item_by_code.get(code, "?")
        city_codes = item_cities.get(code, set())
        city_names = sorted(city_by_code.get(c, c) for c in city_codes)
        if city_names:
            parts.append(f"{name} [{code}]: {', '.join(city_names)}")
        else:
            parts.append(f"{name} [{code}]: unavailable")

    output = "\n".join(parts)
    if len(output.encode("utf-8")) > 495:
        output = output.encode("utf-8")[:495].decode("utf-8", errors="ignore")

    app.logger.info(f"RESPONSE: {output}")
    return jsonify({"output": output})


if __name__ == "__main__":
    app.run(port=5001, debug=False)
