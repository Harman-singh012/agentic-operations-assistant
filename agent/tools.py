"""The agent's three tools: RAG policy search, read-only inventory SQL, external FX API."""
import json
import re

import requests
from django.conf import settings
from django.db import connection, transaction
from langchain_core.tools import tool

from . import vectorstore

MAX_ROWS = 50


# 1) ChromaDB / RAG -----------------------------------------------------------
@tool
def search_policies(query: str) -> str:
    """Search the company policy knowledge base (returns and RMA, procurement approvals,
    reordering rules). Use for any question about policy, process, limits or eligibility.
    Returns the most relevant excerpts, each prefixed with its [source file]."""
    hits = vectorstore.search(query, k=4)
    if not hits:
        return "No matching policy text found."
    return "\n\n".join(f"[{h['source']}] {h['text']}" for h in hits)


# 2) SQL ----------------------------------------------------------------------
_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|replace|truncate|attach|detach|pragma|vacuum|"
    r"grant|revoke|merge|call|exec|execute|load_extension|pg_\w+)\b|--|/\*",
    re.I,
)


def _validate_select(sql: str) -> str:
    s = sql.strip().rstrip(";").strip()
    if not s.lower().startswith("select"):
        raise ValueError("only SELECT statements are allowed")
    if ";" in s:
        raise ValueError("send a single statement")
    if _FORBIDDEN.search(s):
        raise ValueError("statement contains a forbidden keyword or comment")
    tables = {t.strip('"').lower() for t in re.findall(r"\b(?:from|join)\s+([\w.\"]+)", s, re.I)}
    if tables != {"product_inventory"}:
        raise ValueError("only the product_inventory table may be queried")
    return s


@tool
def query_inventory(sql: str) -> str:
    """Run a read-only SQL SELECT against the inventory database and get rows back as JSON.
    Table: product_inventory(sku TEXT, name TEXT, category TEXT, warehouse TEXT, supplier TEXT,
    quantity_on_hand INT, reorder_level INT, unit_price_usd DECIMAL, updated_at DATETIME).
    Categories: Laptops, Accessories, Displays, Servers, Networking.
    A product needs reordering when quantity_on_hand <= reorder_level. Max 50 rows.
    If the tool returns an error, fix the query and try again."""
    try:
        safe = _validate_select(sql)
    except ValueError as exc:
        return f"Rejected: {exc}"
    try:
        with transaction.atomic():
            with connection.cursor() as cur:
                cur.execute(f"SELECT * FROM ({safe}) AS q LIMIT {MAX_ROWS}")
                cols = [c[0] for c in cur.description]
                rows = [dict(zip(cols, r)) for r in cur.fetchall()]
            transaction.set_rollback(True)  # belt and braces: nothing can persist
    except Exception as exc:  # surfaced to the agent so it can self-correct
        return f"SQL error: {exc}"
    return json.dumps(rows, default=str) if rows else "Query returned no rows."


# 3) External API -------------------------------------------------------------
@tool
def convert_currency(amount: float, from_currency: str, to_currency: str) -> str:
    """Convert an amount between currencies using live ECB reference rates (Frankfurter API).
    Use for supplier quotes, cost estimates or showing inventory value in a local currency.
    Currency codes are ISO 4217, e.g. USD, MYR, EUR, SGD."""
    base, target = from_currency.upper().strip(), to_currency.upper().strip()
    try:
        r = requests.get(settings.FX_API_URL, params={"base": base, "symbols": target}, timeout=8)
        r.raise_for_status()
        data = r.json()
        rate = float(data["rates"][target])
    except (requests.RequestException, KeyError, ValueError) as exc:
        return f"Exchange-rate service unavailable or currency unsupported: {exc}"
    return json.dumps({
        "amount": amount, "from": base, "to": target, "rate": rate,
        "converted": round(amount * rate, 2), "rate_date": data.get("date"),
    })


TOOLS = [search_policies, query_inventory, convert_currency]
