import os
import requests
from tavily import TavilyClient
from dotenv import load_dotenv

load_dotenv()

_client = None


def _get_client():
    global _client
    if _client is None:
        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            raise ValueError("TAVILY_API_KEY is not set in environment variables")
        _client = TavilyClient(api_key=api_key)
    return _client


def tavily_search(query: str, max_results: int = 5):
    """General-purpose web search for a deep-dive on a specific trending theme."""
    client = _get_client()
    response = client.search(query=query, max_results=max_results, search_depth="advanced")

    results = []
    for item in response.get("results", []):
        results.append({
            "Title": item.get("title"),
            "Content": item.get("content"),
            "Link": item.get("url"),
            "Score": item.get("score"),
        })
    return results


def verify_url(url: str, timeout: int = 8) -> bool:
    """Lightweight liveness check for a source URL. Returns True if reachable."""
    if not url:
        return False
    try:
        resp = requests.head(url, allow_redirects=True, timeout=timeout)
        if resp.status_code < 400:
            return True
        # Some servers don't support HEAD properly, fall back to GET
        resp = requests.get(url, allow_redirects=True, timeout=timeout, stream=True)
        return resp.status_code < 400
    except requests.RequestException:
        return False


if __name__ == "__main__":
    print(tavily_search("AI agent frameworks"))
