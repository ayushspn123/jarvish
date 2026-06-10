"""Web tools: search the web and fetch/summarize a page's readable text.

Search uses DuckDuckGo (no API key needed). Summarizing fetches a page and returns its
extracted text — the brain (the LLM) does the actual summarizing from that text.
"""

from __future__ import annotations

import requests
from bs4 import BeautifulSoup

from .registry import tool

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}


@tool(
    name="web_search",
    description="Search the web and return the top results (title, URL, snippet).",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query."},
            "max_results": {
                "type": "integer",
                "description": "How many results to return (default 5).",
            },
        },
        "required": ["query"],
    },
)
def web_search(query: str, max_results: int = 5) -> str:
    # `ddgs` is the maintained successor to `duckduckgo_search`.
    try:
        from ddgs import DDGS
    except ImportError:  # pragma: no cover - fallback for older package name
        from duckduckgo_search import DDGS  # type: ignore

    results = []
    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=max(1, min(max_results, 10))):
            results.append(r)

    if not results:
        return f"No results for '{query}'."

    lines = []
    for i, r in enumerate(results, 1):
        title = r.get("title", "(no title)")
        url = r.get("href") or r.get("url", "")
        body = (r.get("body") or "").strip()
        lines.append(f"{i}. {title}\n   {url}\n   {body}")
    return "\n".join(lines)


@tool(
    name="fetch_page",
    description=(
        "Fetch a web page and return its readable text content. "
        "Use this to summarize an article or read a URL the owner gives you."
    ),
    parameters={
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "Full URL to fetch (http/https)."},
        },
        "required": ["url"],
    },
)
def fetch_page(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    resp = requests.get(url, headers=_HEADERS, timeout=20)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "aside"]):
        tag.decompose()

    title = soup.title.string.strip() if soup.title and soup.title.string else ""
    text = " ".join(soup.get_text(separator=" ").split())
    text = text[:8000] + ("...[truncated]" if len(text) > 8000 else "")
    return f"TITLE: {title}\n\n{text}"
