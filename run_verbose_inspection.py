"""
run_verbose_inspection.py
A standalone diagnostic runner that executes one complete newsletter generation run
and records/prints every thinking step, tool call, raw intermediate draft, critique verdict,
rewrite, and URL verification.
Does NOT modify state.py.
"""

import asyncio
import os
import re
import sys
from typing import TypedDict, Annotated
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
load_dotenv()

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_core.tools import BaseTool
from langgraph.prebuilt import ToolNode

from prompt import system_prompt, critique_prompt, revise_instruction_template
from html_parser import convert_md_to_html
from tools.tavily_tool import verify_url

today = datetime.now(timezone.utc).strftime("%B %d, %Y")
TRACE_LOG_PATH = Path("latest_run_trace.log")

log_entries = []

def trace(title: str, content: str = ""):
    divider = "=" * 80
    output = f"\n{divider}\n📌 {title}\n{divider}"
    if content:
        output += f"\n{content}"
    print(output)
    log_entries.append(output)

MAX_REVISIONS = 1

llm = ChatOpenAI(
    model="meta-llama/Llama-3.3-70B-Instruct",
    base_url="https://api.deepinfra.com/v1/openai",
    api_key=os.getenv("DEEPINFRA_API_KEY"),
)

SERVERS = {
    "AI NewsLetter Research": {
        "transport": "stdio",
        "command": sys.executable,
        "args": [str(Path(__file__).parent / "mcp_server.py")]
    }
}

client = MultiServerMCPClient(SERVERS)

async def load_mcp_tools() -> list[BaseTool]:
    try:
        return await client.get_tools()
    except Exception as e:
        trace("ERROR LOADING MCP TOOLS", str(e))
        return []

mcp_tools = asyncio.run(load_mcp_tools())

class NewsletterState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    draft: str
    critique_notes: str
    revision_count: int
    final_html: str

step_counter = 0

async def inspect_call_model(state: dict):
    global step_counter
    step_counter += 1
    trace(f"STEP {step_counter}: AGENT REASONING (LLM INVOCATION)", "Sending prompt and history to Llama-3.3-70B-Instruct...")
    
    messages = state["messages"]
    system_msg = SystemMessage(content=system_prompt)
    llm_with_tools = llm.bind_tools(mcp_tools)
    
    response = await llm_with_tools.ainvoke([system_msg] + messages)
    
    if getattr(response, "tool_calls", None):
        tc_summary = "\n".join(f"  ➜ {tc.get('name')}({tc.get('args')})" for tc in response.tool_calls)
        trace(f"AGENT TOOL CALL DECISION ({len(response.tool_calls)} tools requested)", tc_summary)
    else:
        trace("AGENT DRAFTING COMPLETE (No further tool calls)", f"Initial raw markdown generated ({len(response.content.split())} words):\n\n{response.content}")
        
    return {"messages": [response]}

async def inspect_execute_tools(state: dict):
    global step_counter
    step_counter += 1
    last_msg = state["messages"][-1]
    tool_calls = getattr(last_msg, "tool_calls", [])
    
    trace(f"STEP {step_counter}: EXECUTING TOOLS VIA FASTMCP ({len(tool_calls)} calls)", "Calling tools over stdio...")
    tool_node = ToolNode(mcp_tools)
    result = await tool_node.ainvoke(state)
    
    observations = []
    for tm in result.get("messages", []):
        content = tm.content if hasattr(tm, "content") else str(tm)
        observations.append(f"  [Tool: {getattr(tm, 'name', 'tool')}] Returned {len(content)} characters:\n{content[:400]}...\n")
    
    trace(f"STEP {step_counter}: TOOL OBSERVATIONS RECEIVED", "\n".join(observations))
    return result

def should_continue(state: dict) -> str:
    last_message = state["messages"][-1]
    if getattr(last_message, "tool_calls", None):
        return "tools"
    return "start_critique"

def start_critique(state: dict):
    raw_draft = state["messages"][-1].content
    trace("CAPTURING WORKING DRAFT FOR CRITIQUE", f"Draft captured ({len(raw_draft.split())} words).")
    return {"draft": raw_draft, "revision_count": 0}

async def inspect_critique(state: dict):
    global step_counter
    step_counter += 1
    trace(f"STEP {step_counter}: EDITORIAL CRITIQUE PASS", "Editor agent evaluating draft against 9-point checklist...")
    
    response = await llm.ainvoke([
        SystemMessage(content=critique_prompt),
        HumanMessage(content=state["draft"]),
    ])
    
    notes = response.content.strip()
    is_pass = notes.upper().startswith("PASS")
    
    verdict = "PASSED (Clean)" if is_pass else "REVISION REQUIRED"
    trace(f"CRITIQUE VERDICT: {verdict}", f"Editor Notes:\n{notes}")
    return {"critique_notes": notes}

def route_after_critique(state: dict) -> str:
    notes = state.get("critique_notes", "")
    rev_count = state.get("revision_count", 0)
    
    if notes.strip().upper().startswith("PASS"):
        trace("ROUTING", "Draft passed critique. Moving directly to Source Verification.")
        return "verify_sources"
    
    if rev_count >= MAX_REVISIONS:
        trace("ROUTING", f"Draft reached maximum revision limit ({MAX_REVISIONS}). Moving to Source Verification.")
        return "verify_sources"
    
    trace("ROUTING", f"Triggering Revision pass #{rev_count + 1}...")
    return "revise"

async def inspect_revise(state: dict):
    global step_counter
    step_counter += 1
    rev_idx = state.get("revision_count", 0) + 1
    
    trace(f"STEP {step_counter}: WRITER REVISION PASS #{rev_idx}", f"Revising based on critique feedback:\n{state['critique_notes']}")
    
    instruction = revise_instruction_template.format(critique_notes=state["critique_notes"])
    response = await llm.ainvoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=state["draft"]),
        HumanMessage(content=instruction),
    ])
    
    revised = response.content
    trace(f"REVISION #{rev_idx} OUTPUT ({len(revised.split())} words)", revised)
    return {
        "draft": revised,
        "revision_count": rev_idx,
    }

LINK_PATTERN = re.compile(r"\[([^\]]+)\]\((https?://[^\s)]+)\)")

def inspect_verify_sources(state: dict):
    global step_counter
    step_counter += 1
    draft = state["draft"]
    links = LINK_PATTERN.findall(draft)
    trace(f"STEP {step_counter}: SOURCE LINK LIVENESS VERIFICATION", f"Found {len(links)} links to verify with HTTP HEAD/GET.")
    
    verified = []
    
    def strip_dead_link(match: re.Match) -> str:
        label, url = match.group(1), match.group(2)
        alive = verify_url(url)
        if alive:
            verified.append(f"  ✔ [ALIVE] {label} -> {url}")
            return match.group(0)
        else:
            verified.append(f"  ✖ [DEAD / STRIPPED] {label} -> {url} (Converted to plain text)")
            return label

    cleaned = LINK_PATTERN.sub(strip_dead_link, draft)
    trace("VERIFICATION RESULTS", "\n".join(verified))
    return {"draft": cleaned}

def inspect_final_html(state: dict):
    global step_counter
    step_counter += 1
    trace(f"STEP {step_counter}: COMPILING HTML EMAIL", "Converting markdown to responsive email HTML...")
    html = convert_md_to_html(state["draft"], is_file=False)
    trace("HTML COMPILATION COMPLETE", f"Generated email HTML ({len(html)} bytes).")
    return {"final_html": html}

# Build graph
graph = StateGraph(NewsletterState)
graph.add_node("agent", inspect_call_model)
graph.add_node("tools", inspect_execute_tools)
graph.add_node("start_critique", start_critique)
graph.add_node("critique", inspect_critique)
graph.add_node("revise", inspect_revise)
graph.add_node("verify_sources", inspect_verify_sources)
graph.add_node("final_html", inspect_final_html)

graph.add_edge(START, "agent")
graph.add_conditional_edges("agent", should_continue, ["tools", "start_critique"])
graph.add_edge("tools", "agent")
graph.add_edge("start_critique", "critique")
graph.add_conditional_edges("critique", route_after_critique, ["revise", "verify_sources"])
graph.add_edge("revise", "critique")
graph.add_edge("verify_sources", "final_html")
graph.add_edge("final_html", END)

workflow = graph.compile()

initial_state = {
    "messages": [
        HumanMessage(content="Write this week's AI high-signal newsletter. You must use your tools to gather the latest news, papers, github repos, hackernews stories, hugging face trends, and products before writing the draft.")
    ],
    "revision_count": 0,
}

async def run_inspection():
    trace("INSPECTION SESSION STARTED", f"Target Date: {today}\nLLM: DeepInfra (Llama 3.3 70B Instruct)")
    result = await workflow.ainvoke(initial_state)
    
    trace("INSPECTION COMPLETE - SAVING ARTIFACTS")
    Path("Newsletter_mds").mkdir(exist_ok=True)
    Path("Newsletter_html").mkdir(exist_ok=True)
    
    md_out = Path(f"Newsletter_mds/{today}.md")
    html_out = Path(f"Newsletter_html/{today}.html")
    
    with open(md_out, "w", encoding="utf-8") as f:
        f.write(result["draft"])
    with open(html_out, "w", encoding="utf-8") as f:
        f.write(result["final_html"])
    with open(TRACE_LOG_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(log_entries))
        
    trace("FINISHED", f"Trace log saved to: {TRACE_LOG_PATH.resolve()}\nMarkdown saved to: {md_out.resolve()}\nHTML saved to: {html_out.resolve()}")

if __name__ == "__main__":
    asyncio.run(run_inspection())
