from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Annotated
from datetime import datetime, timezone
from pathlib import Path
import asyncio
import os
import re
import smtplib
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage
from langgraph.graph.message import add_messages
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_core.tools import BaseTool
from langgraph.prebuilt import ToolNode

from prompt import system_prompt, critique_prompt, revise_instruction_template
from html_parser import convert_md_to_html, html_to_plaintext
from tools.tavily_tool import verify_url
from dotenv import load_dotenv

load_dotenv()

MAX_REVISIONS = 1

llm = ChatOpenAI(
    model="meta-llama/Llama-3.3-70B-Instruct",
    base_url="https://api.deepinfra.com/v1/openai",
    api_key=os.getenv("DEEPINFRA_API_KEY"),
)

today = datetime.now(timezone.utc).strftime("%B %d, %Y")

SERVERS = {
    "AI NewsLetter Research": {
        "transport": "stdio",
        "command": sys.executable,
        "args": [
            str(Path(__file__).parent / "mcp_server.py")
        ]
    }
}


class NewsletterState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    draft: str
    critique_notes: str
    revision_count: int
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
    return {"messages": [response]}


tool_node = ToolNode(mcp_tools)


def should_continue(state: NewsletterState) -> str:
    last_message = state["messages"][-1]
    if getattr(last_message, "tool_calls", None):
        return "tools"
    return "start_critique"


def start_critique(state: NewsletterState):
    """Capture the freshly-drafted newsletter as the working draft."""
    return {"draft": state["messages"][-1].content, "revision_count": 0}


async def critique(state: NewsletterState):
    draft = state["draft"]
    response = await llm.ainvoke([
        SystemMessage(content=critique_prompt),
        HumanMessage(content=draft),
    ])
    return {"critique_notes": response.content.strip()}


def route_after_critique(state: NewsletterState) -> str:
    notes = state.get("critique_notes", "")
    revision_count = state.get("revision_count", 0)

    if notes.strip().upper().startswith("PASS"):
        return "verify_sources"

    if revision_count >= MAX_REVISIONS:
        return "verify_sources"

    return "revise"


async def revise(state: NewsletterState):
    instruction = revise_instruction_template.format(critique_notes=state["critique_notes"])
    response = await llm.ainvoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=state["draft"]),
        HumanMessage(content=instruction),
    ])
    return {
        "draft": response.content,
        "revision_count": state.get("revision_count", 0) + 1,
    }


LINK_PATTERN = re.compile(r"\[([^\]]+)\]\((https?://[^\s)]+)\)")


def verify_sources(state: NewsletterState):
    draft = state["draft"]

    def strip_dead_link(match: re.Match) -> str:
        label, url = match.group(1), match.group(2)
        if verify_url(url):
            return match.group(0)
        return label

    cleaned = LINK_PATTERN.sub(strip_dead_link, draft)
    return {"draft": cleaned}


def final_html(state: NewsletterState):
    html_output = convert_md_to_html(state["draft"], is_file=False)
    return {"final_html": html_output}


def send_email(state: NewsletterState):
    recipients_raw = os.getenv("NEWSLETTER_RECIPIENTS", "")
    recipients = [r.strip() for r in recipients_raw.split(",") if r.strip()]

    if not recipients:
        return {}

    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")

    if not smtp_user or not smtp_password:
        return {}

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"AI Weekly – {today}"
    msg["From"] = smtp_user
    msg["To"] = ", ".join(recipients)

    msg.attach(MIMEText(html_to_plaintext(state["final_html"]), "plain"))
    msg.attach(MIMEText(state["final_html"], "html"))

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_user, recipients, msg.as_string())

    return {}


graph = StateGraph(NewsletterState)

graph.add_node("agent", call_model)
graph.add_node("tools", tool_node)
graph.add_node("start_critique", start_critique)
graph.add_node("critique", critique)
graph.add_node("revise", revise)
graph.add_node("verify_sources", verify_sources)
graph.add_node("final_html", final_html)
graph.add_node("send_email", send_email)

graph.add_edge(START, 'agent')
graph.add_conditional_edges("agent", should_continue, ["tools", "start_critique"])
graph.add_edge("tools", "agent")
graph.add_edge("start_critique", "critique")
graph.add_conditional_edges("critique", route_after_critique, ["revise", "verify_sources"])
graph.add_edge("revise", "critique")
graph.add_edge("verify_sources", "final_html")
graph.add_edge("final_html", "send_email")
graph.add_edge("send_email", END)

workflow = graph.compile()

initial_state = {
    "messages": [
        HumanMessage(content="Write this week's AI high-signal newsletter. You must use your tools to gather the latest news, papers, github repos, hackernews stories, hugging face trends, and products before writing the draft.")
    ],
    "revision_count": 0,
}

if __name__ == "__main__":
    Newsletter = asyncio.run(workflow.ainvoke(initial_state))

    Path("./Newsletter_html").mkdir(exist_ok=True)
    Path("./Newsletter_mds").mkdir(exist_ok=True)

    with open(f"./Newsletter_html/{today}.html", "w", encoding="utf-8") as f:
        f.write(Newsletter["final_html"])

    with open(f"./Newsletter_mds/{today}.md", "w", encoding="utf-8") as f:
        f.write(Newsletter["draft"])
