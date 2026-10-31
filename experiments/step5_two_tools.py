import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

import requests
from langchain_ollama import ChatOllama
from langchain_core.tools import tool
from langchain_core.messages import BaseMessage
from langgraph.prebuilt import create_react_agent
from inventory.models import ProductInventory


@tool
def check_inventory(product_name: str) -> str:
    """Check stock quantity and price (in USD) of a laptop by name. Use this for any stock or price question."""
    items = ProductInventory.objects.filter(name__icontains=product_name)
    if not items:
        return "NOT_FOUND: this product is not in the inventory."
    lines = [f"{i.name} has {i.quantity} units in stock, price ${i.price} USD" for i in items]
    return "FOUND: " + "; ".join(lines)


@tool
def get_exchange_rate(base: str, target: str) -> str:
    """Get the live currency exchange rate from base currency to target currency.
    Use 3-letter codes, for example base='USD', target='INR'."""
    try:
        r = requests.get(
            "https://api.frankfurter.dev/v1/latest",
            params={"base": base.upper(), "symbols": target.upper()},
            timeout=10,
        )
        if r.status_code != 200:
            return "NOT_FOUND: could not get that exchange rate."
        data = r.json()
        rate = data["rates"][target.upper()]
        return f"FOUND: 1 {base.upper()} = {rate} {target.upper()} (date {data['date']})"
    except Exception as e:
        return f"NOT_FOUND: exchange rate service error ({e})"


SYSTEM_PROMPT = """You are an operations assistant for a laptop company.

Tools:
- check_inventory: stock and price in USD of laptops.
- get_exchange_rate: live currency exchange rate.

After a tool replies:
- If the reply starts with FOUND, answer using the numbers from the reply.
- If the reply starts with NOT_FOUND, say exactly: I don't have that information.

If a question needs both tools (for example a price in another currency), call check_inventory first, then get_exchange_rate, then multiply the numbers.

If the question is not about company inventory or currency rates, say exactly: I can only help with company operations questions.
Never guess numbers."""

llm = ChatOllama(model="llama3.2:3b", temperature=0)
agent = create_react_agent(llm, [check_inventory, get_exchange_rate], prompt=SYSTEM_PROMPT)

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
                print("OBSERVATION:", msg.content)
            elif msg.type == "ai":
                print("FINAL ANSWER:", msg.content)