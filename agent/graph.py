"""ReAct agent as an explicit LangGraph: reason -> (tool calls) -> act -> reason ... -> answer."""
import re
from functools import lru_cache
from typing import Annotated, TypedDict

from django.conf import settings
from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from .tools import TOOLS

SYSTEM_PROMPT = """You are the Enterprise Operations Assistant. You help operations staff with
policy questions, inventory questions and cost conversions. Work in a ReAct loop:

1. Before EVERY tool call, write one short sentence starting with "Thought:" saying what you
   need and why.
2. Pick the right tool: search_policies for policy/process/limits, query_inventory for stock,
   prices and reorder status, convert_currency for live exchange rates.
3. Read the observation, then continue or answer. Combine tools when needed (for example,
   find items to reorder, then check the approval limit for the order value).

Rules: never invent policy text, stock figures or exchange rates; cite policy source file names;
if tools return nothing, say so. You are read-only and cannot change any data.
Final answers: concise, plain language, no "Thought:" prefix."""


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]


@lru_cache(maxsize=1)
def get_agent():
    llm = init_chat_model(settings.AGENT_MODEL, temperature=0).bind_tools(TOOLS)

    def reason(state: AgentState):
        return {"messages": [llm.invoke([SystemMessage(SYSTEM_PROMPT), *state["messages"]])]}

    g = StateGraph(AgentState)
    g.add_node("reason", reason)
    g.add_node("act", ToolNode(TOOLS))
    g.add_edge(START, "reason")
    g.add_conditional_edges("reason", tools_condition, {"tools": "act", END: END})
    g.add_edge("act", "reason")
    # MemorySaver keeps per-thread history in-process. Swap for SqliteSaver/PostgresSaver
    # when running more than one worker.
    return g.compile(checkpointer=MemorySaver())


def _text(content) -> str:
    if isinstance(content, str):
        return content
    return "".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")


def run_agent_events(question: str, thread_id: str):
    """Yield (event_name, payload) tuples as the graph executes."""
    config = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": settings.AGENT_MAX_STEPS * 2 + 1,
    }
    stream = get_agent().stream({"messages": [HumanMessage(question)]}, config, stream_mode="updates")
    for update in stream:
        for _node, payload in update.items():
            if not isinstance(payload, dict):
                continue
            for msg in payload.get("messages", []):
                if isinstance(msg, AIMessage):
                    text = re.sub(r"^\s*Thought:\s*", "", _text(msg.content)).strip()
                    if msg.tool_calls:
                        if text:
                            yield "thought", {"text": text}
                        for call in msg.tool_calls:
                            yield "action", {"id": call["id"], "tool": call["name"], "input": call["args"]}
                    else:
                        yield "final", {"text": text or "(no answer returned)"}
                elif isinstance(msg, ToolMessage):
                    yield "observation", {
                        "id": msg.tool_call_id, "tool": msg.name, "text": _text(msg.content)[:4000],
                    }
