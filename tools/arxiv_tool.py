import requests
import xml.etree.ElementTree as ET
import re

ARXIV_CATEGORIES = ["cs.AI", "cs.CL", "cs.LG", "cs.CV"]


def search_arxiv(query: str = "artificial intelligence", max_results: int = 5):
    """
    Search arXiv for top recent AI research papers.
    Queries arXiv across cs.AI, cs.CL, cs.LG, cs.CV or specific query,
    extracts title, authors, summary, link, and direct PDF link.
    """
    url = "http://export.arxiv.org/api/query"

    if query and query.lower() not in ("artificial intelligence", "ai", "machine learning"):
        search_query = f'all:"{query}"'
    else:
        # Multi-category query
        search_query = " OR ".join(f"cat:{cat}" for cat in ARXIV_CATEGORIES)

    params = {
        "search_query": search_query,
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }

    paper_info = []

    try:
        response = requests.get(url, params=params, timeout=12)
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            ns = {"atom": "http://www.w3.org/2005/Atom"}

            for entry in root.findall("atom:entry", ns):
                title_elem = entry.find("atom:title", ns)
                summary_elem = entry.find("atom:summary", ns)
                id_elem = entry.find("atom:id", ns)
                published_elem = entry.find("atom:published", ns)

                if title_elem is None or id_elem is None:
                    continue

                title = re.sub(r"\s+", " ", title_elem.text.strip())
                summary = re.sub(r"\s+", " ", (summary_elem.text if summary_elem is not None else "").strip())
                link = id_elem.text.strip()

                authors = entry.findall("atom:author", ns)
                author_names = [a.find("atom:name", ns).text for a in authors if a.find("atom:name", ns) is not None]

                published = published_elem.text if published_elem is not None else ""
                published_date = published.split("T")[0] if "T" in published else published

                # Generate direct PDF link (e.g., http://arxiv.org/abs/2610.1234 -> https://arxiv.org/pdf/2610.1234.pdf)
                pdf_link = link.replace("http://arxiv.org/abs/", "https://arxiv.org/pdf/")
                if not pdf_link.endswith(".pdf"):
                    pdf_link += ".pdf"

                paper_info.append({
                    "Title": title,
                    "Publisher": "arXiv",
                    "Authors": ", ".join(author_names[:4]) + (" et al." if len(author_names) > 4 else ""),
                    "Published_on": published_date,
                    "Summary": summary[:300] + "..." if len(summary) > 300 else summary,
                    "Link": link,
                    "Pdf_link": pdf_link,
                })
    except Exception as e:
        print(f"[arxiv_tool] ArXiv query error: {e}")

    # Fallback to Semantic Scholar if arXiv returns no results
    if len(paper_info) < max_results:
        try:
            ss_url = "https://api.semanticscholar.org/graph/v1/paper/search"
            ss_params = {
                "query": query or "artificial intelligence",
                "limit": max_results,
                "fields": "title,authors,abstract,url,openAccessPdf,publicationDate",
            }
            resp = requests.get(ss_url, params=ss_params, timeout=8)
            if resp.status_code == 200:
                seen_titles = {p["Title"].lower() for p in paper_info}
                for item in resp.json().get("data", []):
                    title = item.get("title", "").strip()
                    if not title or title.lower() in seen_titles:
                        continue
                    authors_list = [a.get("name") for a in item.get("authors", []) if a.get("name")]
                    paper_info.append({
                        "Title": title,
                        "Publisher": "Semantic Scholar",
                        "Authors": ", ".join(authors_list[:3]),
                        "Published_on": item.get("publicationDate") or "",
                        "Summary": (item.get("abstract") or "")[:300],
                        "Link": item.get("url") or "",
                        "Pdf_link": (item.get("openAccessPdf") or {}).get("url") or "",
                    })
                    if len(paper_info) >= max_results:
                        break
        except Exception:
            pass

    return paper_info[:max_results]


if __name__ == "__main__":
    papers = search_arxiv(max_results=3)
    print(f"Fetched {len(papers)} papers:")
    for p in papers:
        print(f"- {p['Title']} by {p['Authors']} | {p['Pdf_link']}")