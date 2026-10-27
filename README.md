<div align="center">

# 🤖 AI Newsletter Agent

### *An Autonomous ReAct Agent that Researches, Critiques, and Publishes High-Signal Tech Newsletters*

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![LangGraph](https://img.shields.io/badge/LangGraph-Agent-green.svg)](https://www.langchain.com/langgraph)
[![MCP](https://img.shields.io/badge/MCP-Protocol-purple.svg)](https://modelcontextprotocol.io/)
[![LLM](https://img.shields.io/badge/Powered%20by-DeepInfra%20(Llama%203.3%2070B)-orange.svg)](https://deepinfra.com/)

**AI Newsletter Agent** is an autonomous, multi-agent editorial workflow that dynamically queries real-time technical sources, verifies link liveness, executes an editorial self-critique loop, and renders a production-grade HTML email newsletter with automated delivery.

</div>

---

## 🌟 Key Capabilities

### 🧠 **Autonomous ReAct Reasoning with Multi-Tier Fallbacks**
The agent operates over the **Model Context Protocol (MCP)** via a decoupled **FastMCP** server. Every research tool is built with a primary API and an automated fallback layer to guarantee data availability:

* **AI News** ([`tools/news_tool.py`](file:///c:/Karm/Projects/AI-Newsletter/tools/news_tool.py)):
  * *Primary*: NewsAPI querying AI/ML topics from the past 7 days.
  * *Fallback / Enrichment*: 6 curated RSS feeds (**TechCrunch AI**, **The Verge AI**, **MIT Tech Review**, **VentureBeat AI**, **Ars Technica**, **Wired AI**) parsed via `feedparser`, deduplicated, and filtered for freshness.
* **ArXiv Papers** ([`tools/arxiv_tool.py`](file:///c:/Karm/Projects/AI-Newsletter/tools/arxiv_tool.py)):
  * *Primary*: arXiv Atom API targeted across categories `cs.AI`, `cs.CL`, `cs.LG`, `cs.CV`, automatically synthesizing direct PDF download links (`https://arxiv.org/pdf/<id>.pdf`).
  * *Fallback*: Semantic Scholar API with rate-limit protection.
* **GitHub Trending** ([`tools/github_tool.py`](file:///c:/Karm/Projects/AI-Newsletter/tools/github_tool.py)):
  * *Primary*: GitHub Search API with `created:>DATE` (last 7 days) and stars sorting, supporting `GITHUB_TOKEN` to avoid rate limits.
  * *Fallback*: Scrapes `github.com/trending?since=weekly` using `BeautifulSoup`.
* **Product Hunt** ([`tools/product_hunt_tool.py`](file:///c:/Karm/Projects/AI-Newsletter/tools/product_hunt_tool.py)):
  * *Primary*: Product Hunt GraphQL v2 API (`PRODUCT_HUNT_TOKEN`).
  * *Fallback*: Product Hunt public RSS feed parsed with AI keyword filtering.
* **Hacker News** ([`tools/hackernews_tool.py`](file:///c:/Karm/Projects/AI-Newsletter/tools/hackernews_tool.py)):
  * Algolia HN Search API pulling top AI discussions (>50 points) from the past 7 days.
* **Hugging Face** ([`tools/huggingface_tool.py`](file:///c:/Karm/Projects/AI-Newsletter/tools/huggingface_tool.py)):
  * Fetches trending open-source weights and daily research papers.
* **Web Deep-Dive** ([`tools/tavily_tool.py`](file:///c:/Karm/Projects/AI-Newsletter/tools/tavily_tool.py)):
  * Tavily search integration allowing the model one focused follow-up investigation into recurring themes.

---

### 🧐 **Self-Critique & Revision Loop**
Drafts are not published blindly. A dedicated editor pass judges the draft against a strict 9-point checklist:
1. **Length**: 600–900 words.
2. **Sections**: All 8 sections present + closing `🔦 SPOTLIGHT`.
3. **Format**: Every Paper, Repo, and Product formatted as `**[Title](url)**`.
4. **Negative Constraints**: Zero tolerance for AI buzzwords (`"game-changer"`, `"revolutionary"`, `"cutting-edge"`, `"in today's fast-paced world"`, `"unlock the power of"`).
5. **Hook Openers**: Required tension/numbers/questions (no flat summaries).
6. **Anti-Leak Prose**: Natural fused sentences; no echoing template instruction labels.

If issues are found, the editor returns actionable feedback and routes to a `revise` node (capped at 1 revision pass).

---

### 🔗 **Automated Source Link Verification**
Before rendering, the graph extracts every markdown URL and executes an HTTP `HEAD`/`GET` check. Dead or unreachable links are stripped back to plain text to prevent broken links in subscriber inboxes.

---

### 🎨 **Responsive HTML Email Template**
[`html_parser.py`](file:///c:/Karm/Projects/AI-Newsletter/html_parser.py) compiles markdown into an email-client-compatible HTML layout featuring:
* Gradient hero header card.
* Color-coded section cards (blue, purple, sky blue, dark slate, green, orange, amber).
* Pull-quote Big Story block with a call-to-action button.
* Dedicated Amber callout card for the **Spotlight**.
* Star count pill badges for GitHub repositories.
* Automatic plaintext fallback generation (`html_to_plaintext`) for multipart MIME delivery.

---

### 📊 **Quality Evaluations (Evals)**
Run [`evals/run_evals.py`](file:///c:/Karm/Projects/AI-Newsletter/evals/run_evals.py) to validate any issue:
* **Structural Checks** ([`evals/structural_checks.py`](file:///c:/Karm/Projects/AI-Newsletter/evals/structural_checks.py)): Deterministic verification of word counts, required sections, source links, banned buzzwords, and well-formed HTML tags.
* **LLM-as-a-Judge** ([`evals/llm_judge.py`](file:///c:/Karm/Projects/AI-Newsletter/evals/llm_judge.py)): Scores curiosity and non-obvious builder angles on a 1–5 scale, saving trend history in `evals/scores/<date>.json`.

---

## 🔄 The LangGraph Architecture

```
[START]
   │
   ▼
[agent] ◄──────────────┐ (7 research tools + 1 deep-dive web search)
   │                   │
   ├─ (tool_calls?) ──►[tools (ToolNode)]
   │
   └─ (draft ready)
           │
           ▼
    [start_critique]
           │
           ▼
       [critique] ◄─────────┐
           │                │
           ├─ (needs fix?) ─►[revise] (capped at MAX_REVISIONS = 1)
           │
           ▼ (PASS or cap reached)
    [verify_sources] (checks URL liveness via HTTP HEAD/GET, strips dead links)
           │
           ▼
      [final_html] (renders email HTML)
           │
           ▼
      [send_email] (dispatches MIME email via Gmail SMTP)
           │
           ▼
         [END]
```

---

## 🚀 Quick Start

### 1. Installation

```bash
git clone https://github.com/yourusername/AI-Newsletter.git
cd AI-Newsletter
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Copy `.env.example` to `.env` and fill in your keys:

```bash
cp .env.example .env
```

```text
# --- Research Sources ---
NEWS_API_KEY=your_news_api_key
PRODUCT_HUNT_TOKEN=your_product_hunt_token
TAVILY_API_KEY=your_tavily_api_key
GITHUB_TOKEN=your_github_token_optional

# --- LLM Generation (DeepInfra) ---
DEEPINFRA_API_KEY=your_deepinfra_key

# --- Tracing (Optional) ---
LANGCHAIN_TRACING_V2=true
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
LANGCHAIN_API_KEY=your_langsmith_key
LANGCHAIN_PROJECT=AI Newsletter Agent

# --- Email Delivery (SMTP) ---
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_gmail_app_password
NEWSLETTER_RECIPIENTS=subscriber1@example.com,subscriber2@example.com
```

---

## 💻 Usage

### Generate and Deliver Newsletter
To kick off the autonomous pipeline (research, draft, critique, verify, render, and email):
```bash
python state.py
```
Outputs are automatically written to `Newsletter_mds/<Date>.md` and `Newsletter_html/<Date>.html`, and delivered to `NEWSLETTER_RECIPIENTS`.

### Run Step-by-Step Diagnostic Inspection
To execute a fully instrumented run that records every tool call, intermediate draft, critique notes, and URL check to a trace log without altering production files:
```bash
python run_verbose_inspection.py
```
Generates a complete execution trace in `latest_run_trace.log`.

### Run Content Quality Evaluations
To score the latest generated newsletter for structural compliance and curiosity/non-obviousness:
```bash
python evals/run_evals.py
```

---

## ⏱️ Automated Scheduling (GitHub Actions)

[`.github/workflows/newsletter.yml`](file:///c:/Karm/Projects/AI-Newsletter/.github/workflows/newsletter.yml) automates publication:
* **Trigger**: Scheduled weekly cron (Mondays at 13:00 UTC) + manual trigger (`workflow_dispatch`).
* **Execution**: Runs in a Python 3.12 runner, runs `state.py`, executes quality evals, and commits the newly generated `.md` and `.html` files directly back to the repository.

Add your credentials under your repository's **Settings ➔ Secrets and variables ➔ Actions**.

---

## 🛠️ Tech Stack

- **LangGraph**: Orchestrates the cyclic agent, critique, revision, and delivery graph.
- **FastMCP**: Decouples and serves data tools over standard I/O (`stdio`).
- **DeepInfra**: High-throughput inference for `meta-llama/Llama-3.3-70B-Instruct`.
- **Tavily**: Powers search deep-dives and URL liveness verification.
- **Feedparser & BeautifulSoup**: Extracts and parses curated RSS feeds and trending web sources.
- **LangSmith**: Full-graph tracing and observability.
- **GitHub Actions**: Automated CI/CD scheduled execution.

---

<div align="center">

**Made with ❤️ by Saish**

⭐ Star this repo if you find it useful!

</div>