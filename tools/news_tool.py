import requests
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
load_dotenv()

def get_ai_news_last_week(page_size=10):
    today = datetime.utcnow()
    last_week = today - timedelta(days=7)

    API_KEY = os.getenv("NEWS_API_KEY", "")
    if not API_KEY:
        raise ValueError("NEWS_API_KEY is not set in environment variables")

    url = (
        'https://newsapi.org/v2/everything?'
        'q=%28%22Artificial%20Intelligence%22%20OR%20%22machine%20learning%22%29%20AND%20%28research%20OR%20breakthrough%20OR%20innovation%20OR%20startup%20OR%20funding%20OR%20investment%20OR%20business%29&'
        f'from={last_week.strftime("%Y-%m-%d")}&'
        f'to={today.strftime("%Y-%m-%d")}&'
        'sortBy=relevancy&'
        'language=en&'
        'searchIn=title,description&'
        f'pageSize={page_size}&'
        f'apiKey={API_KEY}'
    )

    response = requests.get(url)
    response.raise_for_status()  

    data = response.json()

    news_info = []
    for article in data.get("articles", []):
        article_dict = {
            "title": article.get("title"),
            "description": article.get("description"),
            "url": article.get("url"),
            "published_at": article.get("publishedAt"),
            "source": article.get("source", {}).get("name")
        }
        news_info.append(article_dict)

    return news_info

print(get_ai_news_last_week())