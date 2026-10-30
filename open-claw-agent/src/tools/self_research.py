"""
Research and recommendation helpers with web + local LLM fallback.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import requests
from bs4 import BeautifulSoup


def _extract_real_url(raw_url: str) -> str:
    if "duckduckgo.com/l/?" not in raw_url:
        return raw_url
    parsed = urlparse(raw_url)
    params = parse_qs(parsed.query)
    if "uddg" not in params:
        return raw_url
    return unquote(params["uddg"][0])


def web_search(query: str, max_results: int = 8, timeout: int = 20) -> list[dict]:
    """
    Lightweight DuckDuckGo HTML scraping.
    """
    try:
        resp = requests.post(
            "https://html.duckduckgo.com/html/",
            data={"q": query},
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                )
            },
            timeout=timeout,
        )
        if resp.status_code != 200:
            return []
        soup = BeautifulSoup(resp.text, "html.parser")
        out: list[dict] = []
        seen: set[str] = set()
        for result in soup.select(".result"):
            a_tag = result.select_one(".result__a")
            if not a_tag:
                continue
            href = str(a_tag.get("href") or "").strip()
            if not href:
                continue
            url = _extract_real_url(href)
            if not url or url in seen:
                continue
            seen.add(url)
            title = a_tag.get_text(" ", strip=True)
            snippet_tag = result.select_one(".result__snippet")
            snippet = snippet_tag.get_text(" ", strip=True) if snippet_tag else ""
            out.append({"title": title, "url": url, "snippet": snippet})
            if len(out) >= max_results:
                break
        return out
    except Exception:
        return []


def _sources_block(items: list[dict], limit: int = 6) -> str:
    if not items:
        return "No external sources found."
    lines = ["Sources:"]
    for idx, item in enumerate(items[:limit], start=1):
        title = item.get("title", "Untitled source")
        url = item.get("url", "")
        lines.append(f"{idx}. {title} - {url}")
    return "\n".join(lines)


async def _summarize_with_ollama(topic: str, snippets: list[dict], depth: str) -> tuple[bool, str]:
    try:
        from src.tools.ollama_agent import ask_ollama

        compact = []
        for item in snippets[:8]:
            compact.append(f"- {item.get('title', '')}: {item.get('snippet', '')} ({item.get('url', '')})")
        context = "\n".join(compact) if compact else "- no snippets available"
        if depth == "quick":
            prompt = (
                f"Summarize topic '{topic}' in 6 bullet points.\n"
                f"Use this context:\n{context}\n"
                "Keep it practical."
            )
        elif depth == "deep":
            prompt = (
                f"Perform deep analysis of '{topic}'.\n"
                "Include: market signal, opportunities, risks, competitors, next actions.\n"
                f"Context:\n{context}"
            )
        else:
            prompt = (
                f"Analyze '{topic}' for a practical assistant.\n"
                "Give concise sections: What it is, Why it matters now, What to do next.\n"
                f"Context:\n{context}"
            )
        ok, answer = await ask_ollama(prompt)
        return (True, answer) if ok else (False, answer)
    except Exception as exc:
        return False, f"LLM summary error: {exc}"


async def research_topic(
    topic: str,
    depth: str = "medium",
    *,
    include_web: bool = True,
    max_results: int = 8,
) -> tuple[bool, str]:
    query = (topic or "").strip()
    if not query:
        return False, "Research topic is empty."

    snippets = web_search(query, max_results=max_results) if include_web else []
    ok_llm, summary = await _summarize_with_ollama(query, snippets, depth)
    if not ok_llm:
        if snippets:
            fallback = [f"Topic: {query}", "Quick source digest:"]
            for item in snippets[:5]:
                fallback.append(f"- {item.get('title', '')}: {item.get('snippet', '')}")
            fallback.append("")
            fallback.append(_sources_block(snippets))
            return True, "\n".join(fallback)
        return False, summary

    final = summary.strip()
    if snippets:
        final = f"{final}\n\n{_sources_block(snippets)}"
    return True, final


def suggest_for_event(event_text: str) -> list[str]:
    text = (event_text or "").lower()
    common = [
        "Set two reminders: 24h and 2h before start.",
        "Keep a 20-30 minute travel buffer.",
        "Prepare a checklist and required documents in advance.",
    ]
    if any(k in text for k in ["бизнес", "делов", "встреч", "переговор", "интервью"]):
        return [
            "Send a one-page agenda to participants.",
            "Confirm location and expected outcome before meeting.",
            "Prepare fallback venue options in walking distance.",
            *common,
        ]
    if any(k in text for k in ["свидан", "date", "вечерин", "праздник"]):
        return [
            "Book a place early and verify reservation by phone.",
            "Check weather and choose indoor backup option.",
            "Plan route and return trip in advance.",
            *common,
        ]
    if any(k in text for k in ["поездк", "travel", "вылет", "поезд"]):
        return [
            "Re-check tickets and IDs the day before.",
            "Track delays and gate/platform changes.",
            "Pack chargers and essentials in hand luggage.",
            *common,
        ]
    return common


def _infer_city(event_text: str) -> str | None:
    lowered = (event_text or "").lower()
    city_markers = ["в москве", "москва", "в питере", "питер", "санкт-петербург", "in moscow"]
    for marker in city_markers:
        if marker in lowered:
            if "питер" in marker or "санкт" in marker:
                return "Saint Petersburg"
            return "Moscow"
    return None


async def suggest_places_for_event(event_text: str, city: str | None = None) -> tuple[bool, str]:
    city_name = city or _infer_city(event_text) or "your city"
    lowered = (event_text or "").lower()
    if any(k in lowered for k in ["делов", "бизнес", "встреч", "переговор"]):
        place_type = "quiet cafes and business lunch places near metro"
    elif any(k in lowered for k in ["свидан", "date", "вечер"]):
        place_type = "cozy restaurants and interesting date spots"
    else:
        place_type = "comfortable places with easy transport access"

    query = f"{city_name} {place_type}"
    sources = web_search(query, max_results=8)
    try:
        from src.tools.ollama_agent import ask_ollama

        context = "\n".join(
            f"- {item.get('title', '')}: {item.get('snippet', '')}" for item in sources[:8]
        ) or "- no web snippets"
        prompt = (
            "User has an upcoming event.\n"
            f"Event: {event_text}\n"
            f"City: {city_name}\n"
            "Provide 5 place suggestions with short reasons, "
            "considering transport convenience and meeting context.\n"
            f"Context:\n{context}"
        )
        ok, answer = await ask_ollama(prompt)
        if not ok:
            return False, answer
        return True, f"{answer}\n\n{_sources_block(sources)}"
    except Exception as exc:
        if not sources:
            return False, f"Place suggestion error: {exc}"
        lines = ["Place ideas from web results:"]
        for item in sources[:5]:
            lines.append(f"- {item.get('title', '')} ({item.get('url', '')})")
        return True, "\n".join(lines)


async def build_meeting_brief(
    event_title: str,
    event_description: str,
    event_start_iso: str | None,
    memory_summary: str = "",
) -> tuple[bool, str]:
    try:
        from src.tools.ollama_agent import ask_ollama

        prompt = (
            "Create concise pre-meeting brief.\n"
            f"Title: {event_title}\n"
            f"Description: {event_description}\n"
            f"Start time: {event_start_iso or 'unknown'}\n"
            f"Known user context:\n{memory_summary}\n"
            "Return sections: goals, preparation checklist, travel/logistics, questions to ask."
        )
        ok, answer = await ask_ollama(prompt)
        return (True, answer) if ok else (False, answer)
    except Exception as exc:
        return False, f"Meeting brief error: {exc}"


async def run_proactive_research_once(
    topics: list[str],
    output_dir: Path,
    *,
    max_sources_per_topic: int = 5,
) -> tuple[bool, str, Path | None, list[str]]:
    clean_topics = [t.strip() for t in topics if t and t.strip()]
    if not clean_topics:
        return False, "No proactive topics configured.", None, []

    output_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    report_path = output_dir / f"proactive_{now}.md"

    lines: list[str] = ["# Proactive Research Update", ""]
    all_sources: list[str] = []
    text_digest: list[str] = []

    for topic in clean_topics:
        query = f"{topic} latest trends"
        results = web_search(query, max_results=max_sources_per_topic)
        lines.append(f"## {topic}")
        if not results:
            lines.append("- No web results fetched.")
            lines.append("")
            continue
        for item in results[:max_sources_per_topic]:
            title = item.get("title", "")
            url = item.get("url", "")
            snippet = item.get("snippet", "")
            lines.append(f"- {title}")
            if snippet:
                lines.append(f"  - {snippet}")
            lines.append(f"  - {url}")
            if url:
                all_sources.append(url)
            if snippet:
                text_digest.append(f"{topic}: {snippet}")
        lines.append("")

    summary = "\n".join(text_digest[:10]) or "No insights yet."
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return True, summary, report_path, all_sources

