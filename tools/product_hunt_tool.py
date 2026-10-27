import os
import requests
import feedparser
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

AI_KEYWORDS = [
    "ai", "machine learning", "gpt", "llm", "neural",
    "deep learning", "model", "copilot", "assistant", "agent"
]


def _fetch_from_product_hunt_api(min_votes: int = 15, max_results: int = 5):
    token = os.getenv("PRODUCT_HUNT_TOKEN")
    if not token:
        return []

    url = "https://api.producthunt.com/v2/api/graphql"
    one_week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

    query = f"""
    {{
    posts(
        first: 50,
        postedAfter: "{one_week_ago}",
        order: VOTES
    ) {{
        edges {{
        node {{
            name
            tagline
            url
            votesCount
            createdAt
            description
        }}
        }}
    }}
    }}
    """

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(url, json={"query": query}, headers=headers, timeout=10)
        if response.status_code != 200:
            return []

        data = response.json()
        filtered_products = []

        for edge in data.get("data", {}).get("posts", {}).get("edges", []):
            product = edge["node"]
            text = (product.get("name", "") + " " + product.get("tagline", "") + " " + (product.get("description") or "")).lower()

            if any(keyword in text for keyword in AI_KEYWORDS):
                if product.get("votesCount", 0) >= min_votes:
                    filtered_products.append(product)

        filtered_products = sorted(
            filtered_products,
            key=lambda x: x.get("votesCount", 0),
            reverse=True
        )

        product_info = []
        for product in filtered_products[:max_results]:
            product_info.append({
                "Name": product.get("name", ""),
                "Tagline": product.get("tagline", ""),
                "Description": product.get("description") or product.get("tagline") or "No description",
                "Votes": product.get("votesCount", 0),
                "Link": product.get("url", ""),
            })

        return product_info
    except Exception as e:
        print(f"[product_hunt_tool] GraphQL API error: {e}")
        return []


def _fetch_from_product_hunt_rss(max_results: int = 5):
    """Fallback: Parse Product Hunt public RSS feed if API token is missing or fails."""
    url = "https://www.producthunt.com/feed"
    products = []
    seen_names = set()

    try:
        feed = feedparser.parse(url)
        for entry in feed.entries[:30]:
            title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()
            summary = entry.get("summary", "") or entry.get("description", "")

            # Strip HTML tags
            clean_summary = summary.replace("<p>", "").replace("</p>", "").strip()
            if "<" in clean_summary:
                import re
                clean_summary = re.sub(r"<[^>]+>", "", clean_summary).strip()

            combined = f"{title} {clean_summary}".lower()
            if any(k in combined for k in AI_KEYWORDS):
                if title not in seen_names:
                    seen_names.add(title)
                    products.append({
                        "Name": title,
                        "Tagline": clean_summary[:100],
                        "Description": clean_summary[:200] if clean_summary else "AI product launched on Product Hunt",
                        "Votes": 25,  # Estimated fallback
                        "Link": link,
                    })

            if len(products) >= max_results:
                break
    except Exception as e:
        print(f"[product_hunt_tool] RSS fallback error: {e}")

    return products


def get_trending_ai_products(min_votes: int = 15, max_results: int = 5):
    """
    Retrieve trending AI products from Product Hunt.
    Primary: GraphQL API v2 with PRODUCT_HUNT_TOKEN
    Fallback: Scrapes Product Hunt RSS feed
    """
    products = _fetch_from_product_hunt_api(min_votes=min_votes, max_results=max_results)

    if len(products) < 3:
        seen = {p["Name"].lower() for p in products}
        rss_products = _fetch_from_product_hunt_rss(max_results=max_results)
        for p in rss_products:
            if p["Name"].lower() not in seen:
                products.append(p)
                seen.add(p["Name"].lower())
            if len(products) >= max_results:
                break

    return products[:max_results]


if __name__ == "__main__":
    prods = get_trending_ai_products()
    print(f"Fetched {len(prods)} products:")
    for p in prods:
        print(f"- {p['Name']} ({p['Votes']} votes): {p['Link']}")