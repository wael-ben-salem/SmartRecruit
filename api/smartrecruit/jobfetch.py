"""Fetch a job description from a link pasted in the dashboard.

Most job boards (LinkedIn public pages, Indeed, Welcome to the Jungle, company career sites)
embed a schema.org JobPosting in JSON-LD: we read that first, then fall back to known
containers, then to the page's visible text.
"""
import json
import re

import httpx
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/126.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9,fr;q=0.8",
}
CONTAINERS = [".show-more-less-html__markup", ".description__text", "#jobDescriptionText",
              "[data-testid=job-section-description]", ".job-description", "article", "main"]


def _html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for br in soup.find_all(["br", "li", "p", "h1", "h2", "h3", "h4"]):
        br.insert_before("\n")
    text = soup.get_text(" ")
    text = re.sub(r"[ \t\xa0]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()


def _from_json_ld(soup: BeautifulSoup) -> tuple[str, str] | None:
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except json.JSONDecodeError:
            continue
        for item in data if isinstance(data, list) else data.get("@graph", [data]):
            if isinstance(item, dict) and item.get("@type") == "JobPosting" and item.get("description"):
                return item.get("title", ""), _html_to_text(item["description"])
    return None


def _looks_like_login(text: str) -> bool:
    head = text[:1500].lower()
    return ("password" in head and "sign in" in head) or "mot de passe" in head


def fetch_job(url: str) -> dict:
    if not re.match(r"^https?://", url):
        raise ValueError("The job link must start with http:// or https://")
    r = httpx.get(url, headers=HEADERS, follow_redirects=True, timeout=30)
    r.raise_for_status()
    # LinkedIn sends expired or private postings to a search / sign-in page: that is not the job
    if "/jobs/view/" in url and "/jobs/view/" not in str(r.url):
        raise ValueError("This posting is no longer public (expired or login required). Paste the job text instead.")
    soup = BeautifulSoup(r.text, "html.parser")
    title = (soup.title.string or "").strip() if soup.title else ""

    found = _from_json_ld(soup)
    if found:
        return {"title": found[0] or title, "text": found[1], "source": "json-ld", "url": str(r.url)}
    for css in CONTAINERS:
        node = soup.select_one(css)
        if node and len(node.get_text(strip=True)) > 300:
            text = _html_to_text(str(node))
            if _looks_like_login(text):
                break
            return {"title": title, "text": text, "source": css, "url": str(r.url)}
    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    text = _html_to_text(str(soup.body or soup))
    if len(text) < 300 or _looks_like_login(text):
        raise ValueError("Could not read a job description on this page (it may require a login). Paste the text instead.")
    return {"title": title, "text": text, "source": "page text", "url": str(r.url)}
