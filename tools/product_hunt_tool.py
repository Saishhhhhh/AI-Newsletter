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

    token = os.getenv("PRODUCT_HUNT_TOKEN")

    if not token:
        raise ValueError("Missing PRODUCT_HUNT_TOKEN in .env file")

    headers = {
        "Authorization": f"Bearer {token}",
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
        if len(product_info) < 5:
            product_info.append({
                "Name": product["name"],
                "Tagline": product["tagline"],
                "Description": product["description"] or "No description",
                "Votes": product["votesCount"],
                "Link": product["url"]
            })
        else:
            break

    return product_info

if __name__ == "__main__":
    print(get_trending_ai_products())