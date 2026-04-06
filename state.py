from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Annotated
from datetime import datetime, timezone
import asyncio
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage
from langgraph.graph.message import add_messages
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_core.tools import BaseTool
from langgraph.prebuilt import ToolNode
from prompt import system_prompt
from html_parser import convert_md_to_html
from dotenv import load_dotenv

load_dotenv()

llm = ChatGroq(model = "openai/gpt-oss-120b")

today = datetime.now(timezone.utc).strftime("%B %d, %Y")

SERVERS = { 
    "AI NewsLetter Research": {
        "transport": "stdio",
        "command": "python",
        "args": [
            "C:\\D Drive\\Karm\\Projects\\AI-Newsletter\\mcp_server.py"
       ]
    }
}

class NewsletterState(TypedDict):
    
    messages: Annotated[list[BaseMessage], add_messages]
    final_html: str

client = MultiServerMCPClient(SERVERS)

async def load_mcp_tools() -> list[BaseTool]:
    try:
        return await client.get_tools()
    except Exception:
        return []
    
mcp_tools = asyncio.run(load_mcp_tools())

async def call_model(state: NewsletterState):

    messages = state['messages']

    system_msg = SystemMessage(content=system_prompt)

    llm_with_tools = llm.bind_tools(mcp_tools)

    response = await llm_with_tools.ainvoke([system_msg] + messages)

    return {"messages":[response]}

tool_node = ToolNode(mcp_tools)

def should_continue(state: NewsletterState) -> str:

    last_message = state["messages"][-1]

    if getattr(last_message, "tool_calls", None):
        return "tools"
    
    return "final_html"

def final_html(state: NewsletterState):

    md_output = state["messages"][-1].content

    html_output = convert_md_to_html(md_output, is_file = False)

    return {"final_html": html_output}

graph = StateGraph(NewsletterState)

graph.add_node("agent", call_model)
graph.add_node("tools", tool_node)
graph.add_node("final_html", final_html)

graph.add_edge(START, 'agent')
graph.add_conditional_edges("agent", should_continue, ["tools", "final_html"])
graph.add_edge("tools", "agent")
graph.add_edge("final_html", END)

workflow = graph.compile()

initial_state = {
    "messages": [
        HumanMessage(content="Write this week's AI high-signal newsletter. You must use your tools to gather the latest news, papers, github repos, and products to get the data before writing the draft.")
    ]
}
Newsletter = asyncio.run(workflow.ainvoke(initial_state))

with open(f"./Newsletter_html/{today}.html", "w", encoding="utf-8") as f:
    f.write(Newsletter['final_html'])

with open(f"./Newsletter_mds/{today}.md", "w", encoding="utf-8") as f:
    f.write(Newsletter['messages'][-1].content)