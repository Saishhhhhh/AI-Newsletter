import requests
import xml.etree.ElementTree as ET

def search_arxiv(query="machine learning", max_results=5):

    url = "http://export.arxiv.org/api/query"
    
    params = {
        "search_query": query,
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending"
    }
    
    response = requests.get(url, params=params)
    
    if response.status_code != 200:
        print("Error fetching data")
        return
    
    # Parse XML response
    root = ET.fromstring(response.content)
    
    # Namespace required for parsing
    ns = {"atom": "http://www.w3.org/2005/Atom"}

    paper_info = []
    
    for entry in root.findall("atom:entry", ns):
        title = entry.find("atom:title", ns).text.strip()
        summary = entry.find("atom:summary", ns).text.strip()
        link = entry.find("atom:id", ns).text.strip()
        authors = entry.findall("atom:author", ns)
        author_names = [author.find("atom:name", ns).text for author in authors]
        published = entry.find("atom:published", ns).text
        
        # print(f"Title: {title}")
        # print(f"publisher: arXiv / Semantic Scholar" )
        # print(f"Authors: {', '.join(author_names)}")
        # print(f"Summary: {summary}")
        # print(f"Link: {link}")
        # print("-" * 80)

        paper_info.append({
        "Title": title,
        "Publisher": "arXiv / Semantic Scholar",
        "Authors": ', '.join(author_names),
        "Published_on": published.split("T")[0],
        "Summary": summary,
        "Link": link
    })

    return paper_info

# Example usage
print(search_arxiv("artificial intelligence", max_results=3))

