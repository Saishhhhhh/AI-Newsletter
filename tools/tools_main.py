from arxiv_tool import search_arxiv
from github_tool import get_top_repos
from news_tool import get_ai_news_last_week
from product_hunt_tool import get_trending_ai_products

def main():
    research_papers = search_arxiv("artificial intelligence", max_results=3)
    github_repos = get_top_repos()
    news_articles = get_ai_news_last_week()
    ai_products = get_trending_ai_products()

    return {
        "arxiv_research": research_papers,
        "github_research": github_repos,
        "ai_news_research": news_articles,
        "product_hunt_research": ai_products
    }

research_date = main()

print(research_date)