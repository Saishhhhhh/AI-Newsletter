import os
import requests
import feedparser
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

RSS_FEEDS = [
    ("TechCrunch AI", "https://techcrunch.com/category/artificial-intelligence/feed/"),
    ("The Verge AI", "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"),
    ("MIT Tech Review", "https://www.technologyreview.com/feed/"),
    ("VentureBeat AI", "https://venturebeat.com/category/ai/feed/"),
    ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/technology-lab"),
    ("Wired AI", "https://www.wired.com/feed/tag/ai/latest/rss"),
]

AI_KEYWORDS = [
    "ai", "artificial intelligence", "machine learning", "llm", "deep learning",
    "gpt", "agent", "reasoning", "model", "anthropic", "openai", "google", "meta"
]


def _fetch_from_news_api(page_size: int = 5):
    today = datetime.now(timezone.utc)
    last_week = today - timedelta(days=7)

    api_key = os.getenv("NEWS_API_KEY", "")
    if not api_key:
        return []

    url = (
        'https://newsapi.org/v2/everything?'
        'q=%28%22Artificial%20Intelligence%22%20OR%20%22machine%20learning%22%29%20AND%20%28research%20OR%20breakthrough%20OR%20innovation%20OR%20startup%20OR%20funding%20OR%20investment%20OR%20business%29&'
        f'from={last_week.strftime("%Y-%m-%d")}&'
        f'to={today.strftime("%Y-%m-%d")}&'
        'sortBy=relevancy&'
        'language=en&'
        'searchIn=title,description&'
        f'pageSize={page_size}&'
        f'apiKey={api_key}'
    )

    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            articles = []
            for article in data.get("articles", []):
                articles.append({
                    "title": article.get("title"),
                    "description": article.get("description") or "",
                    "url": article.get("url"),
                    "published_at": article.get("publishedAt"),
                    "source": article.get("source", {}).get("name") or "NewsAPI"
                })
            return articles
    except Exception:
        pass
    return []


def _fetch_from_rss_feeds(max_results: int = 5):
    """Fallback & enrichment: parse top AI RSS feeds via feedparser."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    articles = []
    seen_links = set()

    for source_name, feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:10]:
                link = entry.get("link", "")
                title = entry.get("title", "").strip()
                if not link or not title or link in seen_links:
                    continue

                # Parse published date if available
                published_dt = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    published_dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                    published_dt = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)

                if published_dt and published_dt < cutoff:
                    continue

                summary = entry.get("summary", "") or entry.get("description", "")
                # Clean basic HTML tags from summary
                clean_summary = summary.replace("<p>", "").replace("</p>", "").strip()
                if len(clean_summary) > 280:
                    clean_summary = clean_summary[:280] + "..."

                # Check AI relevance if from general tech feeds
                text_lower = f"{title} {clean_summary}".lower()
                if not any(k in text_lower for k in AI_KEYWORDS):
                    continue

                seen_links.add(link)
                articles.append({
                    "title": title,
                    "description": clean_summary,
                    "url": link,
                    "published_at": published_dt.isoformat() if published_dt else "",
                    "source": source_name,
                })
        except Exception:
            continue

    return articles[:max_results]


def get_ai_news_last_week(page_size=5):
    """
    Fetch top AI news articles from the past week.
    Primary: NewsAPI
    Fallback / Enrichment: Curated RSS feeds (TechCrunch, The Verge, Wired, Ars Technica, MIT Tech Review, VentureBeat)
    """
    news_items = _fetch_from_news_api(page_size=page_size)

    # If NewsAPI returned fewer than requested items or failed, backfill from curated RSS feeds
    if len(news_items) < page_size:
        seen = {item.get("url") for item in news_items}
        rss_items = _fetch_from_rss_feeds(max_results=page_size * 2)
        for item in rss_items:
            if item["url"] not in seen:
                news_items.append(item)
                seen.add(item["url"])
            if len(news_items) >= page_size:
                break

    return news_items[:page_size]


if __name__ == "__main__":
    articles = get_ai_news_last_week(5)
    print(f"Fetched {len(articles)} articles:")
    for a in articles:
        print(f"- [{a['source']}] {a['title']} ({a['url']})")