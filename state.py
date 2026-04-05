from langgraph.graph import StateGraph, START, END
from typing import TypedDict
from datetime import datetime, timezone
import asyncio
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
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
    
    arxiv_research: str
    ai_news_research: str
    github_research: str
    product_hunt_research: str
    final_md: str
    final_html: str

async def research_data(state: NewsletterState):
    
    client = MultiServerMCPClient(SERVERS)

    tools = await client.get_tools()

    named_tools = {}
    for tool in tools:
        named_tools[tool.name] = tool

    # print("Available tools:", named_tools.keys())

    # news = await named_tools["get_ai_news"].ainvoke({})

    # papers = await named_tools["get_arxiv_papers"].ainvoke({"query": "artificial intelligence", "max_results": 3})

    # github = await named_tools["get_github_trending"].ainvoke({})

    # products = await named_tools["get_ai_products_trending"].ainvoke({})

    results = await asyncio.gather(
    named_tools["get_ai_news"].ainvoke({}),
    named_tools["get_arxiv_papers"].ainvoke({"query": "artificial intelligence", "max_results": 3}),
    named_tools["get_github_trending"].ainvoke({}),
    named_tools["get_ai_products_trending"].ainvoke({})
    )
    news, papers, github, products = results

    return {
        "arxiv_research": papers,
        "ai_news_research": news,
        "github_research": github,
        "product_hunt_research": products
    }

def data_agg_md(state: NewsletterState):
    
    raw_data = f"""
    ArXiv Research: {state.get("arxiv_research", "None")}
    Ai News : {state.get("ai_news_research", "None")}
    Github Trending Repos: {state.get("github_research", "None")}
    Product Hunt: {state.get("product_hunt_research", "None")}
    """
    
    system_prompt = f"""
    You write a tight, high-signal AI newsletter for busy builders. Every sentence earns its place or gets cut.

    BANNED PHRASES (never use these):
    "This highlights...", "This is significant because...", "This development underscores...",
    "which matters because it...", "This is important because...", "It will be interesting to see...",
    "This has the potential to...", "This move is significant for...", "As the industry continues to evolve...",
    "It's essential to stay up-to-date...", "This approach can improve...", "which matters because it demonstrates..."

    STYLE (follow exactly):
    - State facts, then the "so what" — never describe.
    - One idea per sentence. Short sentences win.
    - Be specific and opinionated, not neutral.

    EXAMPLES of the style I want:

    ❌ "Baidu's robotaxis experienced a significant malfunction, freezing in traffic and causing disruptions. This incident highlights the challenges of deploying autonomous vehicles in complex urban environments and the need for robust testing."
    ✅ "Baidu's robotaxis froze mid-intersection in China, blocking traffic for hours. Self-driving cars clearly aren't ready for dense city streets."

    ❌ "This paper explores the concept of online reasoning calibration, which enables large language models to solve difficult tasks more efficiently. The potential impact of this research lies in making AI models more generalized."
    ✅ "Proposes ORCA, a calibration method that cuts LLM reasoning compute by 50% while keeping accuracy. Cheaper inference at scale."

    ❌ "This repository provides a deep dive into the source code of AI agents, which matters because it offers insights into the inner workings of AI systems."
    ✅ "Reverse-engineers how major AI agents actually work under the hood. Essential reading if you're building agents."

    Now follow this EXACT structure:

    # AI Weekly – {today}

    ## 🔥 This Week in AI
    2 sentences MAX. What defined this week? Be specific.

    ## 📰 Big Story
    The biggest development. 3 sharp sentences:
    - What happened.
    - Why it changes things.
    - What to watch next.
    Include the actual URL as [Source URL](the-url-here).

    ## ⚡ Quick Hits
    3-4 bullets ONLY. Each bullet = 1 punchy sentence + [Source URL](the-url-here). Skip minor news.

    ## 📄 Papers Worth Reading
    3 papers. Each one:
    - **[Paper Title](the-url-here)** by Authors
    - What they did (1 sentence)
    - Why you should care (1 sentence)
    - [PDF](the-pdf-url-here)

    ## 🐙 GitHub Spotlight
    3 repos. Each one:
    - **[Repo Name](the-repo-url-here)** — ⭐ N stars this week
    - What + why in 1-2 sentences.

    ## 🎓 One Thing to Learn
    ONE concept. 3-4 sentences. Explain like talking to a smart friend. No jargon.

    ## 🚀 Products
    3 max. Each = **[Product Name](the-product-url-here)** — 1 sentence on why it's worth trying.

    ## 👋 Bottom Line
    2 sentences. The takeaway + what to watch next week.

    CONSTRAINTS:
    - 600-900 words total. Tight.
    - Never drop source links.
    - Never say "no data available."
    """

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Here is the raw research data: \n {raw_data} and the date is: {today}")
    ]

    response = llm.invoke(messages)
    # print("Hi I am from data agg")

    return {"final_md": response.content}

def final_html(state: NewsletterState):

    md_output = state["final_md"]

    html_output = convert_md_to_html(md_output, is_file = False)

    return {"final_html": html_output}

graph = StateGraph(NewsletterState)

graph.add_node("research_data", research_data)
graph.add_node("data_agg_md", data_agg_md)
graph.add_node("final_html", final_html)

graph.add_edge(START, 'research_data')
graph.add_edge("research_data", "data_agg_md")
graph.add_edge("data_agg_md", "final_html")
graph.add_edge("final_html", END)

workflow = graph.compile()

initial_state = {}
Newsletter = asyncio.run(workflow.ainvoke(initial_state))

print(Newsletter['final_md'])

with open(f"./Newsletter_mds/{today}.md", "w", encoding="utf-8") as f:
  f.write(Newsletter['final_md'])

with open(f"./Newsletter_html/{today}.html", "w", encoding="utf-8") as f:
    f.write(Newsletter['final_html'])