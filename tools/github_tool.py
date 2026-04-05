import requests
from datetime import datetime, timedelta, UTC

def get_top_repos():
    keywords = [
        "AI", "LLM", "machine learning", "deep learning",
        "GPT", "transformer", "diffusion", "neural network",
        "RAG", "fine-tuning", "AI agent",
    ]

    last_week = (datetime.now(UTC) - timedelta(days=7)).strftime("%Y-%m-%d")

    all_repos = {}

    for kw in keywords:
        params = {
        "q": f'"{kw}" created:>={last_week} stars:>10',
        "sort": "stars",
        "order": "desc",
        "per_page": 5
        }

        response = requests.get(
            "https://api.github.com/search/repositories",
            params=params
        )

        if response.status_code == 200:
            items = response.json().get("items", [])

            for repo in items:
                # avoid duplicates
                all_repos[repo["html_url"]] = repo

    # sort all collected repos by stars
    sorted_repos = sorted(
        all_repos.values(),
        key=lambda x: x["stargazers_count"],
        reverse=True
    )

    repo_info = []

    for repo in sorted_repos[:5]:

        repo_info.append({
        "Name": repo['name'],
        "description": repo["description"] or "No description available",
        "Stars": repo['stargazers_count'],
        "Link": repo['html_url']
    })
        
    return repo_info

if __name__ == "__main__":
    print(get_top_repos())