#!/usr/bin/env python3
"""
DeepClaw Nova - Autonomous Web Search & Retrieval Tool
Intelligently queries the internet for real-time information, documentation, and live data.
"""

import urllib.request
import urllib.parse
import json
import re
from typing import List, Dict, Any

SEARCH_INTENT_KEYWORDS = [
    "who is", "what is", "latest", "recent", "news", "documentation",
    "pricing", "download", "weather", "stock", "release date", "current"
]

def should_search_online(query: str) -> bool:
    q = query.lower()
    return any(k in q for k in SEARCH_INTENT_KEYWORDS) or "http://" in q or "https://" in q

def execute_web_search(query: str, max_results: int = 5) -> str:
    """
    Executes a web search via DuckDuckGo Instant Answer API & HTML gateway.
    """
    clean_query = query.strip()
    encoded = urllib.parse.quote_plus(clean_query)
    
    # 1. Try DuckDuckGo Instant Answer API
    try:
        api_url = f"https://api.duckduckgo.com/?q={encoded}&format=json&no_html=1&skip_disambig=1"
        req = urllib.request.Request(api_url, headers={"User-Agent": "DeepClaw-Nova/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            results = []
            if data.get("Abstract"):
                results.append(f"**Abstract:** {data['Abstract']} (Source: {data.get('AbstractURL')})")
            
            for topic in data.get("RelatedTopics", [])[:max_results]:
                if isinstance(topic, dict) and "Text" in topic:
                    results.append(f"- {topic['Text']} [Link]({topic.get('FirstURL', '')})")
            
            if results:
                return f"### Search Results for '{query}':\n" + "\n".join(results)
    except Exception:
        pass

    # 2. Fallback HTML Scraping Gateway
    try:
        html_url = f"https://html.duckduckgo.com/html/?q={encoded}"
        req = urllib.request.Request(html_url, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
            # Extract links and snippets
            snippets = re.findall(r'<a class="result__snippet[^>]*>(.*?)</a>', html, re.DOTALL)
            titles = re.findall(r'<a class="result__url[^>]*href="([^"]*)"[^>]*>(.*?)</a>', html, re.DOTALL)
            
            combined = []
            for i in range(min(max_results, len(snippets))):
                snip_clean = re.sub(r"<[^>]+>", "", snippets[i]).strip()
                link = titles[i][0] if i < len(titles) else ""
                combined.append(f"- {snip_clean} [Source]({link})")
            
            if combined:
                return f"### Search Results for '{query}':\n" + "\n".join(combined)
    except Exception as e:
        return f"Web search could not reach online servers: {e}"

    return f"No definitive search results found for '{query}'."

def fetch_webpage_content(url: str, max_chars: int = 4000) -> str:
    """Extracts raw text content from a given web URL."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
            # Basic HTML strip
            text = re.sub(r"<script[^>]*>.*?</script>", "", raw, flags=re.DOTALL)
            text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
            clean_text = re.sub(r"<[^>]+>", " ", text)
            clean_text = re.sub(r"\s+", " ", clean_text).strip()
            return clean_text[:max_chars]
    except Exception as e:
        return f"Failed to retrieve URL {url}: {e}"
