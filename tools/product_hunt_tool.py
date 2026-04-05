import requests
import os
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
load_dotenv()

def get_trending_ai_products(min_votes=20):
    url = "https://api.producthunt.com/v2/api/graphql"

    ai_keywords = [
        "ai", "machine learning", "gpt", "llm", "neural",
        "deep learning", "model", "copilot", "assistant"
    ]

    one_week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

    query = f"""
    {{
      posts(first: 50, postedAfter: "{one_week_ago}") {{
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
        "Authorization": f"Bearer {os.getenv("PRODUCT_HUNT_TOKEN", "")}",
        "Content-Type": "application/json"
    }

    response = requests.post(url, json={"query": query}, headers=headers)

    if response.status_code != 200:
        print("Error:", response.status_code, response.text)
        return []

    data = response.json()

    filtered_products = []

    for edge in data.get("data", {}).get("posts", {}).get("edges", []):
        product = edge["node"]
        text = (product["name"] + " " + product["tagline"]).lower()

        if any(keyword in text for keyword in ai_keywords):
            if product["votesCount"] >= min_votes:
                filtered_products.append(product)

    # Sort by popularity
    filtered_products = sorted(
        filtered_products,
        key=lambda x: x["votesCount"],
        reverse=True
    )

    product_info = []

    for product in filtered_products:
        product_info.append({
            "Name": product["name"],
            "Tagline": product["tagline"],
            "Description": product["description"] or "No description",
            "Votes": product["votesCount"],
            "Link": product["url"]
        })

    return product_info