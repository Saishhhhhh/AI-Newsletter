"""LLM-as-judge eval: scores a draft 1-5 on the AI-POV / curiosity style, for trend
tracking across issues. Requires DEEPINFRA_API_KEY. Writes evals/scores/<date>.json."""

import json
import os
from pathlib import Path
from datetime import datetime, timezone

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

load_dotenv()

JUDGE_PROMPT = """
You are scoring an AI newsletter draft on a 1-5 scale for exactly one dimension:
does it read as genuinely informative and curiosity-inducing (surprising angles,
non-obvious implications, hooks that make you want to keep reading) rather than a
flat, journalist-style recap of events?

1 = pure recap, no implications, no hooks.
3 = states implications but reads flat, no real hooks or surprise.
5 = consistently surprising/non-obvious, strong hooks, feels genuinely curiosity-inducing.

Respond ONLY with JSON: {"score": <int 1-5>, "rationale": "<one or two sentences>"}
"""


def judge_draft(md: str) -> dict:
    api_key = os.getenv("DEEPINFRA_API_KEY")
    if not api_key:
        return {"score": None, "rationale": "DEEPINFRA_API_KEY not set, skipped"}

    llm = ChatOpenAI(
        model="meta-llama/Llama-3.3-70B-Instruct",
        base_url="https://api.deepinfra.com/v1/openai",
        api_key=api_key,
    )

    response = llm.invoke([
        SystemMessage(content=JUDGE_PROMPT),
        HumanMessage(content=md),
    ])

    try:
        result = json.loads(response.content)
    except json.JSONDecodeError:
        result = {"score": None, "rationale": f"Could not parse judge response: {response.content[:200]}"}

    return result


def save_score(result: dict, scores_dir: Path | None = None) -> Path:
    scores_dir = scores_dir or Path(__file__).parent / "scores"
    scores_dir.mkdir(exist_ok=True)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_path = scores_dir / f"{today}.json"

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    return out_path
