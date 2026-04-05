from tools.arxiv_tool import search_arxiv
from tools.github_tool import get_top_repos
from tools.news_tool import get_ai_news_last_week
from tools.product_hunt_tool import get_trending_ai_products
from fastmcp import FastMCP
import json

mcp = FastMCP(
    name = "AI Newsletter Tools",
    instructions=(
        "This MCP server provides tools for generating an AI newsletter. "
        "Available tools include:\n"
        "- get_ai_news: latest AI news\n"
        "- get_arxiv_papers: recent AI research papers\n"
        "- get_github_trending: trending AI GitHub repos\n"
        "- get_ai_products_trending: trending AI tools from Product Hunt\n\n"
        "All tools return structured JSON strings."
    )
)

@mcp.tool()
def get_ai_news() -> str:
    """
    Fetch the latest Artificial Intelligence news articles from the past week.

    This tool retrieves a curated list of recent AI-related news articles,
    including metadata such as title, description, source, and publication date.

    Returns:
        str: A JSON string containing a list of news articles with the following fields:
            - title (str): Title of the article
            - description (str): Brief summary of the article
            - url (str): Direct link to the full article
            - published_at (str): Publication timestamp (ISO format)
            - source (str): Name of the news source

    """
    try:
        response = get_ai_news_last_week()

        if isinstance(response, str):
            return response
        return json.dumps(response, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})

@mcp.tool()
def get_arxiv_papers(query: str = "artificial intelligence", max_results: int = 3) -> str:
    """
    Retrieve recent research papers on Artificial Intelligence from arXiv.

    This tool queries arXiv (and optionally Semantic Scholar metadata)
    to fetch top recent AI-related research papers.

    Returns:
        str: A JSON string containing a list of research papers with:
            - Title (str): Title of the paper
            - Publisher (str): Source platform (e.g., "arXiv / Semantic Scholar")
            - Authors (str): Comma-separated author names
            - Published_on (str): Publication date (YYYY-MM-DD)
            - Summary (str): Abstract or short summary
            - Link (str): URL to the paper
    """

    max_results = min(max_results, 10)
    if not query:
        query = "artificial intelligence"

    try:
        response = search_arxiv(query, max_results)

        if isinstance(response, str):
            return response
        return json.dumps(response, indent=2, default=str)

    except Exception as e:
        return json.dumps({"error": str(e)})

@mcp.tool()
def get_github_trending() -> str:
    """
    Fetch trending GitHub repositories related to Artificial Intelligence.

    This tool retrieves popular AI-related repositories based on activity,
    stars, and community engagement.

    Returns:
        str: A JSON string containing a list of repositories with:
            - Name (str): Repository name
            - description (str): Short description of the project
            - Stars (int): Number of GitHub stars
            - Link (str): URL to the repository
    """
    try:
        response = get_top_repos()

        if isinstance(response, str):
            return response
        return json.dumps(response, indent=2, default=str)

    except Exception as e:
        return json.dumps({"error": str(e)})

@mcp.tool()
def get_ai_products_trending() -> str:
    """
    Retrieve trending AI products from Product Hunt.

    This tool fetches the most popular AI products currently trending,
    based on community votes and engagement.

    Returns:
        str: A JSON string containing a list of products with:
            - Name (str): Product name
            - Tagline (str): Short tagline or slogan
            - Description (str): Detailed description of the product
            - Votes (int): Number of upvotes on Product Hunt
            - Link (str): URL to the product page
    """
    try:
        response = get_trending_ai_products()

        if isinstance(response, str):
            return response
        return json.dumps(response, indent=2, default=str)

    except Exception as e:
        return json.dumps({"error": str(e)})

if __name__ == "__main__":
    mcp.run()