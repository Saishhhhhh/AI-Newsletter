import requests


def get_huggingface_trending(max_models=5, max_papers=3):
    """Fetch trending models and today's daily papers from Hugging Face."""
    result = {"models": [], "papers": []}

    try:
        resp = requests.get(
            "https://huggingface.co/api/trending",
            params={"type": "model", "limit": max_models},
            timeout=10,
        )
        if resp.status_code == 200:
            for entry in resp.json().get("recentlyTrending", [])[:max_models]:
                repo = entry.get("repoData", {})
                if not repo.get("id"):
                    continue
                result["models"].append({
                    "Name": repo["id"],
                    "Likes": repo.get("likes", 0),
                    "Downloads": repo.get("downloads", 0),
                    "Link": f"https://huggingface.co/{repo['id']}",
                })
    except requests.RequestException:
        pass

    try:
        resp = requests.get("https://huggingface.co/api/daily_papers", timeout=10)
        if resp.status_code == 200:
            for entry in resp.json()[:max_papers]:
                paper = entry.get("paper", {})
                result["papers"].append({
                    "Title": paper.get("title"),
                    "Summary": paper.get("summary", ""),
                    "Link": f"https://huggingface.co/papers/{paper.get('id')}" if paper.get("id") else "",
                })
    except requests.RequestException:
        pass

    return result


if __name__ == "__main__":
    print(get_huggingface_trending())
