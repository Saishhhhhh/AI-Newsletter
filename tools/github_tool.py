import os
import requests
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

AI_KEYWORDS = [
    "AI", "LLM", "machine learning", "deep learning",
    "GPT", "transformer", "diffusion", "neural network",
    "RAG", "fine-tuning", "AI agent",
]


def _build_headers():
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "AI-Newsletter-Agent/1.0"
    }
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _fetch_from_github_api(max_results: int = 5):
    last_week = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
    headers = _build_headers()
    all_repos = {}

    for kw in AI_KEYWORDS[:6]:  # Limit to top 6 keywords to stay well within rate limits
        params = {
            "q": f'"{kw}" created:>={last_week} stars:>10',
            "sort": "stars",
            "order": "desc",
            "per_page": 5,
        }

        try:
            response = requests.get(
                "https://api.github.com/search/repositories",
                params=params,
                headers=headers,
                timeout=10,
            )
            if response.status_code == 200:
                items = response.json().get("items", [])
                for repo in items:
                    all_repos[repo["html_url"]] = repo
            elif response.status_code == 403:
                # Rate limited on unauthenticated search
                break
        except Exception:
            continue

    sorted_repos = sorted(
        all_repos.values(),
        key=lambda x: x.get("stargazers_count", 0),
        reverse=True,
    )

    repo_info = []
    for repo in sorted_repos[:max_results]:
        repo_info.append({
            "Name": repo.get("name", "unknown"),
            "description": repo.get("description") or "No description available",
            "Stars": repo.get("stargazers_count", 0),
            "Link": repo.get("html_url", ""),
        })

    return repo_info


def _fetch_trending_page(max_results: int = 5):
    """Fallback: Scrape github.com/trending if Search API is rate limited or returns few results."""
    url = "https://github.com/trending?since=weekly"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    repos = []
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            rows = soup.select("article.Box-row")
            for r in rows:
                h2 = r.select_one("h2 a")
                if not h2:
                    continue
                repo_path = h2.get("href", "").strip().lstrip("/")
                repo_name = repo_path.split("/")[-1] if "/" in repo_path else repo_path
                repo_url = f"https://github.com/{repo_path}"

                desc_elem = r.select_one("p")
                desc = desc_elem.text.strip() if desc_elem else "Trending repository on GitHub"

                # Extract stars
                stars_elem = r.select_one("a[href$='/stargazers']")
                stars_text = stars_elem.text.strip().replace(",", "") if stars_elem else "0"
                try:
                    stars = int(stars_text)
                except ValueError:
                    stars = 100

                # Filter for AI/agent/LLM relevance
                combined = f"{repo_name} {desc}".lower()
                if any(k.lower() in combined for k in AI_KEYWORDS) or len(repos) < 3:
                    repos.append({
                        "Name": repo_name,
                        "description": desc,
                        "Stars": stars,
                        "Link": repo_url,
                    })

                if len(repos) >= max_results:
                    break
    except Exception as e:
        print(f"[github_tool] Trending page scrape error: {e}")

    return repos


def get_top_repos(max_results: int = 5):
    """
    Fetch trending AI GitHub repositories.
    Primary: GitHub Search API with created:>DATE filter
    Fallback: Scrapes github.com/trending?since=weekly
    """
    repos = _fetch_from_github_api(max_results=max_results)

    if len(repos) < 3:
        seen_links = {r["Link"] for r in repos}
        fallback_repos = _fetch_trending_page(max_results=max_results)
        for r in fallback_repos:
            if r["Link"] not in seen_links:
                repos.append(r)
                seen_links.add(r["Link"])
            if len(repos) >= max_results:
                break

    return repos[:max_results]


if __name__ == "__main__":
    top = get_top_repos()
    print(f"Fetched {len(top)} repos:")
    for r in top:
        print(f"- {r['Name']} (stars: {r['Stars']}): {r['Link']}")