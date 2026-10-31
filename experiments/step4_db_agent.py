import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from langchain_ollama import ChatOllama
from langchain_core.tools import tool
from langchain_core.messages import BaseMessage
from langgraph.prebuilt import create_react_agent
from inventory.models import ProductInventory

@tool
def check_inventory(product_name: str) -> str:
    """Check stock quantity and price of a laptop by name. Use this for any stock or price question."""
    items = ProductInventory.objects.filter(name__icontains=product_name)
    if not items:
        return "NOT_FOUND: this product is not in the inventory."
    lines = [f"{i.name} has {i.quantity} units in stock, price ${i.price}" for i in items]
    return "FOUND: " + "; ".join(lines)

SYSTEM_PROMPT = """You are an operations assistant for a laptop company.

Use the check_inventory tool for stock or price questions.

After the tool replies:
- If the reply starts with FOUND, answer using the numbers from the reply. Example: "There are 8 Legion 5 units in stock, priced at $1299."
- If the reply starts with NOT_FOUND, say exactly: I don't have that information.

If the question is not about company inventory, say exactly: I can only help with company operations questions.
Never guess numbers."""

llm = ChatOllama(model="llama3.2:3b", temperature=0)
agent = create_react_agent(llm, [check_inventory], prompt=SYSTEM_PROMPT)

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
    config={"recursion_limit": 8},
):
    for node, data in step.items():
        if not isinstance(data, dict):
            continue
        for msg in as_list(data.get("messages", [])):
            if not isinstance(msg, BaseMessage):
                continue
            if getattr(msg, "tool_calls", None):
                call = msg.tool_calls[0]
                print("ACTION:", call["name"], call["args"])
            elif msg.type == "tool":
                print("OBSERVATION:", msg.content)
            elif msg.type == "ai":
                print("FINAL ANSWER:", msg.content)