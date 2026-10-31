from langchain_ollama import ChatOllama
from langchain_core.tools import tool

# A fake database for now
STOCK = {
    "thinkpad x1": 15,
    "thinkpad t14": 0,
    "legion 5": 8,
    "ideapad 3": 40,
}

@tool
def check_inventory(product_name: str) -> str:
    """Check how many units of a laptop are in stock. Use this for any stock question."""
    key = product_name.lower()
    for name, qty in STOCK.items():
        if key in name or name in key:
            return f"{name}: {qty} in stock"
    return "Product not found in inventory."

llm = ChatOllama(model="llama3.2:3b", temperature=0)
llm_with_tools = llm.bind_tools([check_inventory])

reply = llm_with_tools.invoke("How many ThinkPad X1 are in stock?")
print("Tool calls requested by the AI:")
print(reply.tool_calls)