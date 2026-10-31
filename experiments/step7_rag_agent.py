import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

import requests
from langchain_ollama import ChatOllama
from langchain_core.tools import tool
from langchain_core.messages import BaseMessage
from langgraph.prebuilt import create_react_agent
from inventory.models import ProductInventory
from agent.rag import search


def fetch_rate(base: str, target: str):
    """Return (rate, date) or None if the lookup fails."""
    try:
        r = requests.get(
            "https://api.frankfurter.dev/v1/latest",
            params={"base": base.upper(), "symbols": target.upper()},
            timeout=10,
        )
        if r.status_code != 200:
            return None
        data = r.json()
        return data["rates"][target.upper()], data["date"]
    except Exception:
        return None


@tool
def check_inventory(product_name: str) -> str:
    """Check stock quantity and price (in USD) of a laptop by name. Use for stock or USD price questions."""
    items = ProductInventory.objects.filter(name__icontains=product_name)
    if not items:
        return "NOT_FOUND: this product is not in the inventory."
    lines = [f"{i.name} has {i.quantity} units in stock, price ${i.price} USD" for i in items]
    return "FOUND: " + "; ".join(lines)


@tool
def get_exchange_rate(base: str, target: str) -> str:
    """Get the live exchange rate between two currencies, using 3-letter codes
    (for example base='USD', target='INR'). Use only when asked for a rate, not a laptop price."""
    result = fetch_rate(base, target)
    if result is None:
        return "NOT_FOUND: could not get that exchange rate."
    rate, date = result
    return f"FOUND: 1 {base.upper()} = {rate} {target.upper()} (date {date})"


@tool
def price_in_currency(product_name: str, currency: str) -> str:
    """Get a laptop's price converted into another currency, using a 3-letter code
    (for example currency='INR'). Use for any question like 'price of <laptop> in <currency>'."""
    item = ProductInventory.objects.filter(name__icontains=product_name).first()
    if item is None:
        return "NOT_FOUND: this product is not in the inventory."
    result = fetch_rate("USD", currency)
    if result is None:
        return "NOT_FOUND: could not get that exchange rate."
    rate, date = result
    converted = float(item.price) * rate
    return (f"FOUND: {item.name} costs ${item.price} USD = {converted:,.2f} {currency.upper()} "
            f"(rate 1 USD = {rate} {currency.upper()}, date {date})")


@tool
def search_policy(query: str) -> str:
    """Search the company policy documents (warranty, returns, RMA, battery, support, procurement).
    Use for any policy or procedure question."""
    results = search(query, k=3)
    if not results:
        return "NOT_FOUND: no relevant policy text."
    text = "\n---\n".join(f"[{r.metadata['source']}] {r.page_content}" for r in results)
    return "FOUND: " + text


SYSTEM_PROMPT = """You are an operations assistant for a laptop company.

Tools:
- check_inventory: stock and USD price of laptops.
- get_exchange_rate: live exchange rate between two currencies.
- price_in_currency: a laptop's price converted into another currency.
- search_policy: company policy documents (warranty, returns, RMA, battery, support, procurement).

Call one tool, then answer using only its reply.

For policy questions: read the policy text in the reply and answer the question in one or two short sentences, in your own words. Then add a last line: Source: <file name>. The policy text usually contains the answer, so answer from it.

If a reply starts with NOT_FOUND, say exactly: I don't have that information.

If the question is not about laptop inventory, prices, currency rates or company policy, say exactly: I can only help with company operations questions.
Never guess. Never write a tool call as text."""

llm = ChatOllama(model="llama3.2:3b", temperature=0)
agent = create_react_agent(
    llm,
    [check_inventory, get_exchange_rate, price_in_currency, search_policy],
    prompt=SYSTEM_PROMPT,
)

question = input("Ask something: ")


def as_list(x):
    if isinstance(x, BaseMessage):
        return [x]
    if isinstance(x, (list, tuple)):
        return list(x)
    return []


for step in agent.stream(
    {"messages": [("user", question)]},
    stream_mode="updates",
    config={"recursion_limit": 10},
):
    for node, data in step.items():
        if not isinstance(data, dict):
            continue
        for msg in as_list(data.get("messages", [])):
            if not isinstance(msg, BaseMessage):
                continue
            if getattr(msg, "tool_calls", None):
                for call in msg.tool_calls:
                    print("ACTION:", call["name"], call["args"])
            elif msg.type == "tool":
                print("OBSERVATION:", msg.content[:300].replace("\n", " "))
            elif msg.type == "ai":
                print("FINAL ANSWER:", msg.content)