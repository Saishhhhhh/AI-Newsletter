# 🧠 AI Newsletter — System Architecture

> A production-grade, autonomous newsletter generation pipeline built on **LangGraph**, **FastMCP**, and **Llama 3.3 70B** via DeepInfra. Every issue is researched, written, critiqued, revised, and delivered — entirely by agents.

---

## Visual Overview

![AI Newsletter · LangGraph Architecture](./workflow_graph.png)

---

## Table of Contents

1. [High-Level Design Philosophy](#1-high-level-design-philosophy)
2. [Repository Structure](#2-repository-structure)
3. [Core State Machine — LangGraph](#3-core-state-machine--langgraph)
   - [State Schema](#31-state-schema)
   - [Graph Topology](#32-graph-topology)
4. [Node-by-Node Breakdown](#4-node-by-node-breakdown)
5. [MCP Tool Layer](#5-mcp-tool-layer)
6. [Multi-Tier Tool Fallback Chains](#6-multi-tier-tool-fallback-chains)
7. [Prompt Engineering Layer](#7-prompt-engineering-layer)
8. [HTML Rendering Pipeline](#8-html-rendering-pipeline)
9. [Email Delivery](#9-email-delivery)
10. [Evaluation Layer](#10-evaluation-layer)
11. [CI/CD — GitHub Actions](#11-cicd--github-actions)
12. [Environment & Configuration](#12-environment--configuration)
13. [Data Flow — End-to-End](#13-data-flow--end-to-end)
14. [Key Design Decisions](#14-key-design-decisions)

---

## 1. High-Level Design Philosophy

This system treats newsletter generation as an **agent reasoning problem**, not a scripted pipeline. The core loop is:

```mermaid
flowchart LR
    A["🔍 Research"] --> B["✍️ Draft"]
    B --> C["🧐 Self-Critique"]
    C -->|fail| D["🔄 Revise"]
    D --> C
    C -->|pass| E["🔗 Validate URLs"]
    E --> F["🎨 Render HTML"]
    F --> G["📧 Deliver"]

    style A fill:#1e3a5f,color:#93c5fd
    style B fill:#1e3a5f,color:#93c5fd
    style C fill:#3b1f5e,color:#c4b5fd
    style D fill:#3b1f5e,color:#c4b5fd
    style E fill:#1a3a2f,color:#6ee7b7
    style F fill:#1a3a2f,color:#6ee7b7
    style G fill:#4a1942,color:#f9a8d4
```

Three principles drive every architectural decision:

| Principle | Implementation |
|---|---|
| **Resilience** | Every data source has a primary API + at least one fallback (RSS, scrape, or alternate API) |
| **Editorial Quality** | A separate LLM pass critiques the draft against a strict 9-point checklist before delivery |
| **Zero Human-in-the-Loop** | The graph runs fully autonomously from a single `python state.py` invocation |

---

## 2. Repository Structure

```
AI-Newsletter/
├── state.py                   # LangGraph orchestrator — the entire pipeline lives here
├── mcp_server.py              # FastMCP server exposing 7 research tools over stdio
├── prompt.py                  # All LLM prompts: system_prompt, critique_prompt, revise_template
├── html_parser.py             # Markdown → styled HTML + plaintext fallback
├── requirements.txt           # Python dependencies
├── .env                       # API keys & SMTP credentials (not committed)
├── .env.example               # Template for required env vars
│
├── tools/                     # Individual research tool modules
│   ├── arxiv_tool.py          # arXiv Atom API + Semantic Scholar fallback
│   ├── github_tool.py         # GitHub Search API + trending page scrape fallback
│   ├── news_tool.py           # NewsAPI + 6 curated RSS feeds fallback
│   ├── product_hunt_tool.py   # Product Hunt GraphQL v2 + RSS fallback
│   ├── hackernews_tool.py     # Hacker News Algolia API
│   ├── huggingface_tool.py    # Hugging Face Hub API (models + daily papers)
│   └── tavily_tool.py         # Tavily web search + URL liveness checker
│
├── evals/                     # Quality evaluation layer
│   ├── structural_checks.py   # Offline regex-based section/format validation
│   ├── llm_judge.py           # LLM-powered quality scoring (DeepInfra)
│   └── scores/                # Persisted JSON score history
│
├── .github/
│   └── workflows/
│       └── newsletter.yml     # Scheduled GitHub Actions CI/CD
│
├── Newsletter_mds/            # Output: raw Markdown drafts (one per run)
├── Newsletter_html/           # Output: styled HTML newsletters (one per run)
├── workflow_graph.png         # Architecture diagram
├── architecture.md            # This document
└── run_verbose_inspection.py  # Diagnostic runner — captures full execution traces
```

---

## 3. Core State Machine — LangGraph

### 3.1 State Schema

Defined in `state.py` as a `TypedDict`:

```python
class NewsletterState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]  # Full conversation + tool call history
    draft: str          # Current working draft (Markdown)
    critique_notes: str # Editor feedback from the critique node
    revision_count: int # Number of revision cycles completed
    final_html: str     # Rendered HTML output
```

- `messages` uses LangGraph's `add_messages` reducer — new messages are **appended**, not replaced.
- `draft` is a plain string that gets overwritten by `start_critique` and `revise`.
- `revision_count` gates the maximum number of revision loops (`MAX_REVISIONS = 1`).

### 3.2 Graph Topology

```mermaid
stateDiagram-v2
    direction TB

    [*] --> agent

    agent --> tools        : has tool_calls
    tools --> agent        : tool results appended

    agent --> start_critique : no tool_calls (draft ready)

    start_critique --> critique

    critique --> revise        : REVISE notes
    revise --> critique        : revision_count + 1

    critique --> verify_sources : PASS
    critique --> verify_sources : revision_count >= MAX_REVISIONS

    verify_sources --> final_html
    final_html --> send_email
    send_email --> [*]

    state agent {
        direction LR
        [*] --> llm_invoke
        llm_invoke --> [*]
    }
    state critique {
        direction LR
        [*] --> checklist_9pt
        checklist_9pt --> [*]
    }
```

**Conditional edges:**

| From | Condition | To |
|---|---|---|
| `agent` | `last_message.tool_calls` is non-empty | `tools` |
| `agent` | No tool calls in last message | `start_critique` |
| `critique` | Notes start with `PASS` | `verify_sources` |
| `critique` | `revision_count >= MAX_REVISIONS` | `verify_sources` (force pass) |
| `critique` | Notes start with `REVISE:` | `revise` |
| `revise` | Always | `critique` (loop back) |

---

## 4. Node-by-Node Breakdown

### 4.1 AGENT Node

**File:** `state.py` — `call_model()`

```python
async def call_model(state: NewsletterState):
    messages = state['messages']
    system_msg = SystemMessage(content=system_prompt)
    llm_with_tools = llm.bind_tools(mcp_tools)
    response = await llm_with_tools.ainvoke([system_msg] + messages)
    return {"messages": [response]}
```

**What it does:**
- Injects the full `system_prompt` (builder persona + structure rules) as a `SystemMessage`
- Binds all 7 MCP tools to the LLM so it can call them via OpenAI tool-calling protocol
- Invokes `Llama-3.3-70B-Instruct` asynchronously via DeepInfra's OpenAI-compatible endpoint
- Returns the model response (which may contain tool call requests) to be appended to `messages`

**Model:** `meta-llama/Llama-3.3-70B-Instruct`  
**Provider:** DeepInfra (OpenAI-compatible REST API)  
**Client:** `langchain_openai.ChatOpenAI` with custom `base_url`

---

### 4.2 TOOLS Node

**File:** `state.py` — `ToolNode(mcp_tools)`

**What it does:**
- LangGraph's built-in `ToolNode` receives the tool calls from the last agent message
- Dispatches each call to the corresponding MCP tool via the `langchain_mcp_adapters` bridge
- The MCP client communicates with `mcp_server.py` over **stdio** (not HTTP)
- Tool results are returned as `ToolMessage` objects and appended to `messages`
- Control returns to `agent`, which sees the results and decides whether to call more tools or draft

**Transport:** `stdio` (subprocess)  
**Protocol:** Model Context Protocol (FastMCP)  
**Bridge:** `langchain-mcp-adapters` → `MultiServerMCPClient`

---

### 4.3 START_CRITIQUE Node

**File:** `state.py` — `start_critique()`

```python
def start_critique(state: NewsletterState):
    return {"draft": state["messages"][-1].content, "revision_count": 0}
```

**What it does:**
- A lightweight synchronous "snapshot" node
- Captures the agent's final draft (the last `AIMessage` content) into the `draft` field
- Resets `revision_count` to 0 so the revision loop starts fresh
- Separates the "research phase" from the "editorial phase" cleanly

---

### 4.4 CRITIQUE Node

**File:** `state.py` — `critique()`

```python
async def critique(state: NewsletterState):
    response = await llm.ainvoke([
        SystemMessage(content=critique_prompt),
        HumanMessage(content=draft),
    ])
    return {"critique_notes": response.content.strip()}
```

**What it does:**
- Runs the LLM as a **pure editor** (no tools bound) against a strict 9-point checklist
- The `critique_prompt` checks for: word count, section completeness, link presence, hook quality, buzzword violations, template leakage, and markdown link format correctness
- Responds with either `PASS` (exact string) or `REVISE: <numbered list>`
- Result stored in `critique_notes` for routing and potential revision

**The 9-point checklist:**

| # | Check |
|---|---|
| 1 | Word count ~600–900 |
| 2 | All 9 sections present (including 🔦 SPOTLIGHT) |
| 3 | Every item has a `[Source URL](...)` link |
| 4 | Intro and Big Story open with a hook, not a flat summary |
| 5 | Every item states WHAT happened + the non-obvious implication |
| 6 | At least one item reads as genuinely surprising |
| 7 | No banned buzzwords |
| 8 | No template instruction labels leaked into prose |
| 9 | Papers/repos/products formatted as `**[Title](url)**` |

**Critique → Revise loop:**

```mermaid
flowchart TD
    SC[start_critique\nSnapshot draft into state] --> C

    C["critique\nLlama 3.3 70B as editor"] --> R1{Response?}

    R1 -->|"PASS"| VS[verify_sources]
    R1 -->|"revision_count >= 1"| VS
    R1 -->|"REVISE: ..."| RV

    RV["revise\nFull rewrite from scratch\nrevision_count += 1"] --> C

    VS --> FH[final_html]

    style SC fill:#1e3a5f,color:#93c5fd
    style C fill:#3b1f5e,color:#c4b5fd
    style RV fill:#3b1f5e,color:#c4b5fd
    style VS fill:#1a3a2f,color:#6ee7b7
    style FH fill:#1a3a2f,color:#6ee7b7
    style R1 fill:#2d1b1b,color:#fca5a5
```

---

### 4.5 REVISE Node

**File:** `state.py` — `revise()`

```python
async def revise(state: NewsletterState):
    instruction = revise_instruction_template.format(critique_notes=state["critique_notes"])
    response = await llm.ainvoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=state["draft"]),
        HumanMessage(content=instruction),
    ])
    return {"draft": response.content, "revision_count": state.get("revision_count", 0) + 1}
```

**What it does:**
- Constructs a 3-message conversation: original brief (system) + bad draft + editor notes
- The LLM rewrites the **entire newsletter from scratch**, not just patching
- Increments `revision_count`; the graph will force-exit after `MAX_REVISIONS = 1` cycles
- Returns the new draft, which goes back to `critique` for re-evaluation

---

### 4.6 VERIFY_SOURCES Node

**File:** `state.py` — `verify_sources()`

```python
LINK_PATTERN = re.compile(r"\[([^\]]+)\]\((https?://[^\s)]+)\)")

def verify_sources(state: NewsletterState):
    def strip_dead_link(match):
        label, url = match.group(1), match.group(2)
        if verify_url(url):
            return match.group(0)   # keep intact
        return label                # strip dead link, keep label text
    cleaned = LINK_PATTERN.sub(strip_dead_link, draft)
    return {"draft": cleaned}
```

**What it does:**
- Scans every Markdown hyperlink in the draft via regex
- Makes a live HTTP HEAD/GET request to each URL via `tools/tavily_tool.py::verify_url`
- Dead links (4xx/5xx or timeout) have their URL stripped — the anchor text is preserved
- Prevents broken links from reaching the final HTML output

---

### 4.7 FINAL_HTML Node

**File:** `state.py` — `final_html()`

```python
def final_html(state: NewsletterState):
    html_output = convert_md_to_html(state["draft"], is_file=False)
    return {"final_html": html_output}
```

**What it does:**
- Passes the verified Markdown draft to `html_parser.py::convert_md_to_html`
- The parser applies a rich, styled HTML template (gradient hero, per-section accent cards, pill badges, spotlight callout)
- Returns the complete HTML document in `final_html`
- Also persists both `.md` and `.html` to disk (handled in `__main__` block)

---

### 4.8 SEND_EMAIL Node

**File:** `state.py` — `send_email()`

```python
def send_email(state: NewsletterState):
    msg = MIMEMultipart("alternative")
    msg.attach(MIMEText(html_to_plaintext(state["final_html"]), "plain"))
    msg.attach(MIMEText(state["final_html"], "html"))
    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_user, recipients, msg.as_string())
```

**What it does:**
- Reads comma-separated recipients from `NEWSLETTER_RECIPIENTS` env var
- Builds a `multipart/alternative` MIME message (plaintext + HTML parts)
- Sends via SMTP with STARTTLS — defaults to `smtp.gmail.com:587`
- Silently skips if no recipients or credentials configured (no crash)
- Subject: `"AI Weekly – {today}"` where `today` is UTC date

---

## 5. MCP Tool Layer

### 5.1 FastMCP Server

**File:** `mcp_server.py`

The MCP server is a **separate Python subprocess** that the orchestrator spawns at startup:

```python
SERVERS = {
    "AI NewsLetter Research": {
        "transport": "stdio",
        "command": sys.executable,
        "args": [str(Path(__file__).parent / "mcp_server.py")]
    }
}
client = MultiServerMCPClient(SERVERS)
mcp_tools = asyncio.run(load_mcp_tools())
```

All 7 tools are exposed as MCP-spec tools and automatically converted to LangChain `BaseTool` objects by `langchain-mcp-adapters`. The agent sees them as ordinary function-calling tools.

### 5.2 Tool Catalog

| Tool Name | Source Module | Primary API | Fallback |
|---|---|---|---|
| `get_ai_news` | `news_tool.py` | NewsAPI v2 | 6 RSS feeds via `feedparser` |
| `get_arxiv_papers` | `arxiv_tool.py` | arXiv Atom API | Semantic Scholar Graph API |
| `get_github_trending` | `github_tool.py` | GitHub Search API | `github.com/trending` scrape |
| `get_ai_products_trending` | `product_hunt_tool.py` | Product Hunt GraphQL v2 | Product Hunt RSS feed |
| `get_hackernews_trending` | `hackernews_tool.py` | HN Algolia Search API | — |
| `get_huggingface_trending` | `huggingface_tool.py` | HF Hub REST API | — |
| `search_web` | `tavily_tool.py` | Tavily Search API | — |

---

## 6. Multi-Tier Tool Fallback Chains

### 6.1 News Tool

```mermaid
flowchart LR
    N1["NewsAPI v2\nAI query · last 7 days\nsort: relevancy"] -->|"< 5 results or no key"| N2
    N2["RSS Fallback via feedparser\nTechCrunch AI · The Verge AI\nMIT Tech Review · VentureBeat\nArs Technica · Wired AI"]
    N1 & N2 --> N3["Deduplicate by URL\n→ top 5 articles"]

    style N1 fill:#1e3a5f,color:#93c5fd
    style N2 fill:#2d2a1b,color:#fde68a
    style N3 fill:#1a3a2f,color:#6ee7b7
```

### 6.2 arXiv Tool

```mermaid
flowchart LR
    A1["arXiv Atom API\ncs.AI · cs.CL · cs.LG · cs.CV\nsort: submittedDate desc"] -->|"< max_results"| A2
    A2["Semantic Scholar Graph API\ntitle · authors · abstract\nopenAccessPdf · publicationDate"]
    A1 & A2 --> A3["Deduplicate by title\n→ top N papers + PDF links"]

    style A1 fill:#1e3a5f,color:#93c5fd
    style A2 fill:#2d2a1b,color:#fde68a
    style A3 fill:#1a3a2f,color:#6ee7b7
```

### 6.3 GitHub Tool

```mermaid
flowchart LR
    G1["GitHub Search API\nkeywords: AI LLM GPT RAG ...\ncreated >= 7d ago · stars > 10\nBearer token if GITHUB_TOKEN set"] -->|"< 3 results / rate limited"| G2
    G2["BeautifulSoup scrape\ngithub.com/trending?since=weekly\nAI keyword filter"]
    G1 & G2 --> G3["Deduplicate by URL\n→ top 5 repos"]

    style G1 fill:#1e3a5f,color:#93c5fd
    style G2 fill:#2d2a1b,color:#fde68a
    style G3 fill:#1a3a2f,color:#6ee7b7
```

### 6.4 Product Hunt Tool

```mermaid
flowchart LR
    P1["Product Hunt GraphQL v2\ntopic: artificial-intelligence\nsorted by votes · last 7 days\nBearer PRODUCT_HUNT_TOKEN"] -->|"error / empty"| P2
    P2["Product Hunt RSS feed\nhttps://producthunt.com/feed\nAI keyword filter"]
    P1 & P2 --> P3["→ top 3 AI products"]

    style P1 fill:#1e3a5f,color:#93c5fd
    style P2 fill:#2d2a1b,color:#fde68a
    style P3 fill:#1a3a2f,color:#6ee7b7
```

---

## 7. Prompt Engineering Layer

**File:** `prompt.py`

### 7.1 System Prompt

The system prompt defines the entire editorial persona and output structure. Key elements:

**Persona:**
> "You think like an AI system designer, agent builder, and infrastructure engineer... not a journalist."

**Mandatory research phase:**
- Must call all 6 category tools before writing anything
- May call `search_web` exactly once for a single deep-dive follow-up

**Core writing rule (for every item):**
1. WHAT HAPPENED — the concrete fact
2. WHY IT'S INTERESTING — the non-obvious implication for builders

**Required output structure (9 sections):**

| Section | Emoji | Content |
|---|---|---|
| This Week in AI | 🔥 | 2-sentence hook intro |
| Big Story | 📰 | 3-sentence prose, no labels |
| Quick Hits | ⚡ | 3–4 bullets with source links |
| Papers Worth Reading | 📄 | 3 papers, `**[Title](url)**` format |
| GitHub Spotlight | 🐙 | 3 repos, `**[Name](url)**` format |
| One Thing to Learn | 🎓 | 1 concept, 3–4 sentences |
| Products | 🚀 | 3 max, `**[Name](url)**` format |
| Bottom Line | 👋 | 2-sentence close |
| Spotlight | 🔦 | 1 surprising item callout |

**Banned buzzwords:** `"game-changer"`, `"revolutionary"`, `"cutting-edge"`, `"in today's fast-paced world"`, `"unlock the power of"`

**Word limit:** 600–900 words total

### 7.2 Critique Prompt

A separate prompt that turns the LLM into a **ruthless editor** with no authority to rewrite — only to judge. It checks all 9 criteria and responds with either `PASS` or `REVISE: <numbered list>`.

### 7.3 Revise Instruction Template

```python
revise_instruction_template = """
Your previous draft needs revision. Here is the editor's feedback:

{critique_notes}

Rewrite the FULL newsletter from scratch, fixing every point above, while keeping the
same structure, the same sources/facts you already gathered, and the same style rules
from the original brief.
"""
```

Key design: the LLM is asked to rewrite **from scratch** (not patch), which produces higher-quality revisions.

---

## 8. HTML Rendering Pipeline

**File:** `html_parser.py`

The `convert_md_to_html(draft, is_file=False)` function transforms the Markdown output into a production-quality email-safe HTML document.

**Visual features:**
- **Gradient hero header** — deep blue-to-purple gradient with date and branding
- **Section accent cards** — each section gets its own color-coded card border
- **Spotlight callout** — the `🔦 SPOTLIGHT:` line is extracted and rendered as a full-width highlighted box
- **Pill badges** — source names, emoji headers, and tags rendered as rounded pills
- **Paper cards** — arXiv papers get structured cards with title, authors, summary, and PDF link button
- **GitHub repo cards** — star count, description, and direct link button
- **Product cards** — tagline + CTA button

**Plaintext fallback:**
- `html_to_plaintext(html)` strips all HTML tags for the `text/plain` MIME part of the email

---

## 9. Email Delivery

**Configuring delivery:**

| Env Var | Description | Default |
|---|---|---|
| `NEWSLETTER_RECIPIENTS` | Comma-separated recipient emails | — |
| `SMTP_HOST` | SMTP server hostname | `smtp.gmail.com` |
| `SMTP_PORT` | SMTP port | `587` |
| `SMTP_USER` | Sender email address | — |
| `SMTP_PASSWORD` | App password or SMTP password | — |

**For Gmail:** use an [App Password](https://myaccount.google.com/apppasswords), not your account password.

The email is sent as `multipart/alternative`:
1. `text/plain` — plaintext fallback (for clients that don't render HTML)
2. `text/html` — full styled newsletter (preferred by modern email clients)

---

## 10. Evaluation Layer

**Directory:** `evals/`

```mermaid
flowchart TD
    DRAFT["Final draft.md"] --> SC & LJ

    subgraph SC["structural_checks.py — no LLM, no network"]
        direction TB
        SC1["✅ Word count 550–950"]
        SC2["✅ All 9 section emojis present"]
        SC3["✅ Quick Hits have source links"]
        SC4["✅ No banned buzzwords"]
        SC5["✅ HTML well-formed (tag balance)"]
    end

    subgraph LJ["llm_judge.py — Llama 3.3 70B via DeepInfra"]
        direction TB
        LJ1["Scores 1–5 on curiosity-inducing quality\n1 = flat recap · 5 = strong hooks + non-obvious angles"]
        LJ2["Returns JSON: score + rationale"]
        LJ1 --> LJ2
    end

    SC --> R1{"passed?"}
    R1 -->|yes| OK["✅ PASS — newsletter clean"]
    R1 -->|no| FAIL["❌ issues list returned"]

    LJ2 --> SCORES["evals/scores/{date}.json\ntrend tracking over time"]

    style SC fill:#1a2a1a,color:#86efac
    style LJ fill:#1e1a3a,color:#c4b5fd
    style OK fill:#14532d,color:#86efac
    style FAIL fill:#450a0a,color:#fca5a5
    style SCORES fill:#1c1917,color:#d6d3d1
```

### Structural Checks (`structural_checks.py`)

Offline, no-LLM validation via regex pattern matching:

- All 9 required section emoji/headers are present
- `**[Title](url)**` format is used for papers, repos, and products
- No banned buzzwords in the text
- Word count is within 600–900
- `🔦 SPOTLIGHT:` line is present

### LLM Judge (`llm_judge.py`)

Uses `Llama-3.3-70B-Instruct` via DeepInfra to score the newsletter **1–5** on a single axis:

> *Does it feel genuinely curiosity-inducing (surprising angles, non-obvious implications, strong hooks) — or is it a flat journalist recap?*

Scores are serialized to `evals/scores/{date}.json` for tracking quality over time.

---

## 11. CI/CD — GitHub Actions

**File:** `.github/workflows/newsletter.yml`

The pipeline can run on a **cron schedule** (e.g., every Monday morning) or be manually triggered via `workflow_dispatch`.

```mermaid
flowchart TD
    T(["⏰ cron schedule\nor workflow_dispatch"]) --> A

    A["Checkout repo"] --> B["Set up Python 3.12"]
    B --> C["pip install -r requirements.txt"]
    C --> D["python state.py\n(secrets injected as env vars)"]
    D --> E["Upload artifacts\nNewsletter_html/ · Newsletter_mds/"]
    E --> F["Run structural_checks.py\n(optional quality gate)"]
    F --> G{"passed?"}
    G -->|yes| H["✅ Workflow success"]
    G -->|no| I["❌ Annotate failed checks"]

    style T fill:#1c1917,color:#d6d3d1
    style D fill:#1e3a5f,color:#93c5fd
    style F fill:#1a2a1a,color:#86efac
    style H fill:#14532d,color:#86efac
    style I fill:#450a0a,color:#fca5a5
```

**Required secrets** (set in GitHub repo settings):
- `DEEPINFRA_API_KEY`
- `NEWS_API_KEY`
- `PRODUCT_HUNT_TOKEN`
- `TAVILY_API_KEY`
- `SMTP_USER` / `SMTP_PASSWORD` / `NEWSLETTER_RECIPIENTS`

---

## 12. Environment & Configuration

**File:** `.env.example`

```bash
# LLM Provider
DEEPINFRA_API_KEY=your_deepinfra_key_here

# Research Tools
NEWS_API_KEY=your_newsapi_key_here
PRODUCT_HUNT_TOKEN=your_product_hunt_token_here
TAVILY_API_KEY=your_tavily_key_here
GITHUB_TOKEN=optional_for_higher_rate_limits

# Email Delivery
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password_here
NEWSLETTER_RECIPIENTS=recipient1@email.com,recipient2@email.com
```

**Python environment:** Python 3.12, managed via `.venv/`

**Key dependencies:**

| Package | Role |
|---|---|
| `langgraph` | State machine orchestration |
| `langchain-openai` | OpenAI-compatible LLM client (DeepInfra) |
| `langchain-mcp-adapters` | Bridges MCP tools to LangChain tool format |
| `fastmcp` | FastMCP server framework |
| `feedparser` | RSS feed parsing (news fallback) |
| `beautifulsoup4` | HTML scraping (GitHub trending fallback) |
| `tavily-python` | Web search + URL verification |
| `requests` | HTTP calls for all primary APIs |
| `python-dotenv` | `.env` file loading |

---

## 13. Data Flow — End-to-End

```mermaid
flowchart TD
    START(["python state.py"]) --> INIT

    INIT["LangGraph init\nHumanMessage: 'Write this week...'\nrevision_count = 0"] --> AGENT

    subgraph RESEARCH["Research Phase — AGENT + TOOLS loop"]
        direction LR
        AGENT["Llama 3.3 70B\nwith 7 tools bound"] --> TOOLS
        TOOLS --> T1["get_ai_news → 5 articles"]
        TOOLS --> T2["get_arxiv_papers → 3-5 papers"]
        TOOLS --> T3["get_github_trending → 5 repos"]
        TOOLS --> T4["get_ai_products_trending → 3 products"]
        TOOLS --> T5["get_hackernews_trending → HN stories"]
        TOOLS --> T6["get_huggingface_trending → models + papers"]
        TOOLS --> T7["search_web → 1 deep-dive"]
        T1 & T2 & T3 & T4 & T5 & T6 & T7 --> AGENT
    end

    AGENT -->|"no more tool calls"| SC

    SC["start_critique\nSnapshot draft · reset revision_count"] --> CR

    subgraph EDITORIAL["Editorial Phase"]
        direction TB
        CR["critique\n9-point checklist"] -->|REVISE| RV
        RV["revise\nFull rewrite from scratch"] -->|"revision_count + 1"| CR
        CR -->|"PASS or max revisions"| VS
    end

    VS["verify_sources\nHTTP check every link"] --> FH
    FH["final_html\nMarkdown → styled HTML"] --> SE
    SE["send_email\nSMTP STARTTLS · multipart/alternative"] --> OUT

    OUT["📁 Newsletter_mds/{date}.md\n🌐 Newsletter_html/{date}.html\n📧 Email delivered"]

    style RESEARCH fill:#0f1e30,color:#93c5fd
    style EDITORIAL fill:#1e0f30,color:#c4b5fd
    style VS fill:#0f1e17,color:#6ee7b7
    style FH fill:#0f1e17,color:#6ee7b7
    style SE fill:#2d0f1e,color:#f9a8d4
    style OUT fill:#1c1917,color:#d6d3d1
```

**Typical total runtime:** 3–8 minutes (dominated by 7 tool calls + 2 LLM passes for draft + critique)

---

## 14. Key Design Decisions

### Why LangGraph instead of a linear script?

LangGraph's **conditional edges** make the revision loop natural — the critique result directly controls whether the graph goes to `revise` or proceeds to `verify_sources`. A linear script would require messy `while` loops and manual state management.

### Why FastMCP over direct function calls?

FastMCP lets the LLM **discover tools at runtime** via the MCP protocol, making tool addition/removal trivial. Adding a new data source is just adding a new `@mcp.tool()` function — no changes to `state.py` needed.

### Why stdio transport (not HTTP)?

Stdio keeps the tool server as a local subprocess with zero networking overhead. It starts instantly and stays perfectly synchronized with the orchestrator process lifecycle.

### Why DeepInfra + Llama 3.3 70B?

- **No vendor lock-in** — DeepInfra's OpenAI-compatible API means any `langchain-openai` code works as-is
- **Cost-effective** — inference costs significantly less than GPT-4 class APIs
- **Quality** — Llama 3.3 70B handles structured output, tool calling, and editorial critique reliably

### Why rewrite-from-scratch for revisions?

Asking the LLM to patch a specific section often introduces subtle inconsistencies (different tone, broken formatting). Rewriting the full newsletter from scratch with the editor's notes in context produces cleaner, more coherent output — at the cost of one extra LLM call.

### Why MAX_REVISIONS = 1?

The critique loop is intentionally capped at 1 revision. In practice, the initial draft passes ~70% of the time; the revision pass fixes the remaining cases. More iterations add latency with diminishing returns.

---

*Architecture documented · Last updated: October 2026*
