<div align="center">

# 🤖 AI Newsletter Agent

### *An Autonomous ReAct Agent that Researches and Writes High-Signal Tech Newsletters*

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![LangGraph](https://img.shields.io/badge/LangGraph-Agent-green.svg)](https://www.langchain.com/langgraph)
[![MCP](https://img.shields.io/badge/MCP-Protocol-purple.svg)](https://modelcontextprotocol.io/)
[![LLM](https://img.shields.io/badge/Powered%20by-Groq-orange.svg)](https://groq.com/)

**AI Newsletter Agent** is an autonomous AI workflow that dynamically queries real-time web sources to draft, format, and render a production-grade HTML tech newsletter. 

> **Note:** This is a practice project built specifically to explore and master **Advanced Agentic AI** concepts, including cyclic reasoning (ReAct), conditional routing, and the Model Context Protocol (MCP).

</div>

---

## 🌟 Features

### 🧠 **Autonomous ReAct Reasoning Loop**
Unlike static data pipelines, this agent thinks for itself. It analyzes the user request, decides which research tools to call, evaluates the returned data, and seamlessly recovers if a tool fails—looping continuously until it has enough context to write the draft.

### 🔌 **Decoupled MCP Architecture**
Data fetching is entirely decoupled from the LLM via a custom **FastMCP** server. The agent securely communicates with generic Python tools over `stdio`.
- **Arxiv:** Latest AI research papers.
- **GitHub Trending:** Top AI repositories.
- **News Aggregator:** Top AI headlines of the week.
- **Product Hunt:** Trending AI tools.
- **Hacker News:** High-signal AI stories by points.
- **Hugging Face:** Trending models + daily papers.
- **Web Search (Tavily):** A single follow-up deep-dive the agent can trigger on whichever theme recurs across the other sources.

### 🧭 **Self-Critique + Source Verification Loop**
After drafting, a second LLM pass reviews the draft against a strict checklist (structure, hooks, non-obvious angles, banned buzzwords) and either passes it or sends it back for one bounded revision. Before rendering, every source link in the draft is HEAD-checked and silently stripped if dead.

### 📝 **High-Signal, Curiosity-Driven Writing**
The agent operates under heavily constrained prompt engineering: **negative constraints** (banned buzzwords), **few-shot examples**, required **hooks** (no flat summary openers), and a mandatory **🔦 Spotlight** — the single most surprising/non-obvious item each issue — to strip out "AI-fluff" and keep readers hooked.

### 🎨 **Polished HTML Template + Email Delivery**
The final markdown is parsed into a hand-built, email-client-safe HTML template with a gradient hero band, per-section accent colors, a pull-quote Big Story, and a spotlight callout — then sent via SMTP as a multipart HTML + plaintext email.

### 📊 **Evals**
`evals/run_evals.py` checks every generated issue for structural compliance (word count, required sections, source links, banned words) and runs an LLM-as-judge pass that scores curiosity/non-obviousness 1-5, tracked over time in `evals/scores/`.

### 🤖 **Scheduled via GitHub Actions**
`.github/workflows/newsletter.yml` runs the whole pipeline weekly (and on-demand via `workflow_dispatch`), commits the new issue back to the repo, and emails it out — no manual runs required.

---

## 🔄 The LangGraph Workflow

The core of this project is built on **LangGraph**, using a conditional router to simulate autonomous thought.

<div align="center">
  <img src="./workflow_graph.png" alt="LangGraph Architecture" width="400"/>
</div>

1. **Agent Node:** The LLM evaluates the system prompt and conversation history, calling research tools until it has enough signal, optionally doing one `search_web` deep-dive on a recurring theme.
2. **Critique Node:** A second LLM pass checks the draft against the style/structure checklist and either passes it or requests a revision (capped at one extra pass).
3. **Verify Sources Node:** HEAD-checks every link in the draft and strips any that are dead.
4. **HTML Node:** Parses the final markdown draft into the styled HTML email template.
5. **Send Email Node:** Emails the rendered HTML (with a plaintext fallback) to every address in `NEWSLETTER_RECIPIENTS`.

---

## 🚀 Quick Start

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/AI-Newsletter.git
cd AI-Newsletter
```

2. **Install dependencies**
Ensure you have `uv` installed, or use standard pip targeting a virtual environment:
```bash
pip install -r requirements.txt
```

3. **Set up your environment variables**
Copy `.env.example` to `.env` and fill in your keys:
```bash
cp .env.example .env
```
```text
# Research sources
PRODUCT_HUNT_TOKEN=your_product_hunt_token_here
NEWS_API_KEY=your_news_api_key_here
TAVILY_API_KEY=your_tavily_api_key_here

# LLM generation (DeepInfra, OpenAI-compatible endpoint)
DEEPINFRA_API_KEY=your_deepinfra_api_key_here

# Tracing (optional)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
LANGCHAIN_API_KEY=your_langsmith_key_here
LANGCHAIN_PROJECT=AI Newsletter Agent

# Email delivery (SMTP)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_gmail_app_password
NEWSLETTER_RECIPIENTS=someone@example.com,other@example.com
```

---

## 💻 Usage

To kick off the autonomous agent and generate (and email) this week's newsletter:

```bash
python state.py
```

1. The MCP server will automatically boot up in the background.
2. You can track the agent's reasoning loop and tool execution in your LangSmith dashboard.
3. Once completed, a new `.html` and `.md` file titled with today's date will appear in your output folders, and an email goes out to `NEWSLETTER_RECIPIENTS` (if set).

To score the latest issue for structural compliance and curiosity/non-obviousness:

```bash
python evals/run_evals.py
```

### Running on a schedule

`.github/workflows/newsletter.yml` runs this weekly via GitHub Actions and commits the new
issue back to the repo. Add the following as **repository secrets** (Settings → Secrets and
variables → Actions): `DEEPINFRA_API_KEY`, `NEWS_API_KEY`, `PRODUCT_HUNT_TOKEN`,
`TAVILY_API_KEY`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`,
`NEWSLETTER_RECIPIENTS` (and the `LANGCHAIN_*` ones if you want tracing in CI too). You can
also trigger a run manually from the Actions tab via `workflow_dispatch`.

---

## 🛠️ Tech Stack

- **LangGraph**: Orchestrates the cyclic Agent → Critique → Verify → Email workflow.
- **FastMCP**: Hosts the data-fetching tools securely.
- **DeepInfra**: Serves the LLM (`meta-llama/Llama-3.3-70B-Instruct`) via an OpenAI-compatible API.
- **Tavily**: Powers the agent's deep-dive search and source-liveness checks.
- **LangSmith**: Used for tracing the agent's internal thought process.
- **GitHub Actions**: Runs the pipeline on a weekly schedule.

---

<div align="center">

**Made with ❤️ by Saish**

⭐ Star this repo if you find it useful!

</div>