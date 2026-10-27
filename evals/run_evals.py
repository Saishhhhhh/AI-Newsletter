"""CLI: run structural + LLM-judge evals against the most recent newsletter draft.
Non-blocking by design — prints a report but always exits 0, since this is a
content-quality signal, not a correctness gate."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from evals.structural_checks import run_structural_checks
from evals.llm_judge import judge_draft, save_score


def latest_file(directory: Path, suffix: str) -> Path | None:
    files = sorted(directory.glob(f"*{suffix}"), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def main():
    root = Path(__file__).parent.parent
    md_dir = root / "Newsletter_mds"
    html_dir = root / "Newsletter_html"

    md_path = latest_file(md_dir, ".md")
    if md_path is None:
        print("No newsletter markdown found in Newsletter_mds/. Nothing to evaluate.")
        return

    md_text = md_path.read_text(encoding="utf-8")

    html_path = html_dir / md_path.name.replace(".md", ".html")
    html_text = html_path.read_text(encoding="utf-8") if html_path.exists() else None

    print(f"Evaluating: {md_path.name}\n")

    structural = run_structural_checks(md_text, html_text)
    print("--- Structural checks ---")
    print("PASSED" if structural["passed"] else "FAILED")
    for issue in structural["issues"]:
        print(f"  - {issue}")

    print("\n--- LLM judge (curiosity / non-obviousness) ---")
    judge_result = judge_draft(md_text)
    print(f"  Score: {judge_result.get('score')}")
    print(f"  Rationale: {judge_result.get('rationale')}")

    if judge_result.get("score") is not None:
        out_path = save_score(judge_result)
        print(f"  Saved to {out_path}")


if __name__ == "__main__":
    main()
