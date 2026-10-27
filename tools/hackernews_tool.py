import requests
from datetime import datetime, timedelta, UTC

AI_KEYWORDS = [
    "AI", "LLM", "GPT", "agent", "machine learning", "transformer",
    "diffusion", "RAG", "fine-tuning", "neural network",
]


def get_hackernews_trending(min_points=50, max_results=5):
    """Fetch recent high-signal AI stories from Hacker News (past 7 days)."""
    last_week_ts = int((datetime.now(UTC) - timedelta(days=7)).timestamp())

    all_stories = {}

    for kw in AI_KEYWORDS:
        params = {
            "tags": "story",
            "query": kw,
            "numericFilters": f"created_at_i>{last_week_ts},points>={min_points}",
            "hitsPerPage": 10,
        }

        try:
            response = requests.get(
                "http://hn.algolia.com/api/v1/search_by_date",
                params=params,
                timeout=10,
            )
        except requests.RequestException:
            continue

        if response.status_code != 200:
            continue

        for hit in response.json().get("hits", []):
            story_id = hit.get("objectID")
            if not story_id or not hit.get("title"):
                continue
            all_stories[story_id] = hit

    sorted_stories = sorted(
        all_stories.values(),
        key=lambda h: h.get("points", 0),
        reverse=True,
    )

    story_info = []
    for hit in sorted_stories[:max_results]:
        story_info.append({
            "Title": hit["title"],
            "Points": hit.get("points", 0),
            "Comments": hit.get("num_comments", 0),
            "Link": hit.get("url") or f"https://news.ycombinator.com/item?id={hit['objectID']}",
            "DiscussionLink": f"https://news.ycombinator.com/item?id={hit['objectID']}",
        })

    return story_info


if __name__ == "__main__":
    print(get_hackernews_trending())
