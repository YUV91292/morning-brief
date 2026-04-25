"""
Uses Claude to curate raw RSS articles into a structured editorial digest.
"""
import json
import re
import logging
from typing import Any

import anthropic
from json_repair import repair_json

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the editor-in-chief of a premium daily global news digest called
"The Morning Global Brief". Your reader is Urvil Bumiya, a sophisticated professional who
follows global politics, business, technology, climate, and has strong interest in India, UAE,
and US developments.

Your job: curate raw article headlines/summaries from RSS feeds into a polished, insightful
morning briefing. Write like the Economist meets the FT — sharp, clear, globally-minded.

RULES:
- Select 14-18 total stories. Prioritise significance, freshness, and editorial balance.
- Do NOT copy article text wholesale. Write original 3-5 sentence summaries in your own voice.
- Paraphrase; do not quote long passages verbatim. Short (under 15 word) direct quotes are ok.
- Each story must have: headline, 3-5 sentence editorial summary, "why_it_matters" (1 sentence),
  source_links (1-3 URLs), and section assignment.
- Assign each story to exactly one section from the list provided.
- The "Front Page" section must have 1 lead story + 2-3 secondary stories.
- "Markets at a Glance" and "What to Watch Next" are special sections handled separately.
- IMPORTANT: Use only double quotes inside JSON. Never use apostrophes in JSON string values.
- Return ONLY valid JSON — no markdown fences, no commentary outside the JSON.
"""

USER_PROMPT_TEMPLATE = """Today is {date}.

SECTIONS AVAILABLE: {sections}

RAW ARTICLES (title | source | summary | link):
{articles_text}

Return a JSON object with this structure:
{{
  "edition_date": "...",
  "lead_headline": "...",
  "lead_intro": "...",
  "sections": [
    {{
      "name": "Front Page",
      "stories": [
        {{
          "headline": "...",
          "summary": "...",
          "why_it_matters": "...",
          "source_links": ["url1", "url2"],
          "is_lead": true,
          "image_url": "",
          "image_caption": "",
          "image_credit": ""
        }}
      ]
    }}
  ],
  "what_to_watch": ["One-sentence forward-looking item", "..."],
  "editors_note": "Optional 1-sentence note from the editor"
}}

Important: "Markets at a Glance" is injected separately — do NOT include it in your output."""


def articles_to_text(articles: list[dict]) -> str:
    lines = []
    for i, a in enumerate(articles[:180], 1):
        lines.append(
            f"{i}. [{a['source']}] {a['title']}\n"
            f"   {a['summary'][:300]}\n"
            f"   URL: {a['link']}\n"
        )
    return "\n".join(lines)


def _try_parse(raw: str) -> dict:
    """Try increasingly aggressive methods to parse JSON from Claude response."""
    # 1. Direct parse
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # 2. Auto-repair (handles unescaped quotes, apostrophes, trailing commas etc.)
    try:
        repaired = repair_json(raw, return_objects=True)
        if isinstance(repaired, dict) and repaired:
            return repaired
    except Exception:
        pass
    # 3. Extract outermost { } then repair
    m = re.search(r'\{.*\}', raw, re.DOTALL)
    if m:
        try:
            repaired = repair_json(m.group(0), return_objects=True)
            if isinstance(repaired, dict) and repaired:
                return repaired
        except Exception:
            pass
    raise ValueError("Could not parse JSON from Claude response")


def curate_digest(articles: list[dict], date_str: str, sections: list[str], api_key: str) -> dict[str, Any]:
    client = anthropic.Anthropic(api_key=api_key)
    articles_text = articles_to_text(articles)
    user_prompt = USER_PROMPT_TEMPLATE.format(
        date=date_str,
        sections=", ".join(s for s in sections if s != "Markets at a Glance"),
        articles_text=articles_text,
    )
    log.info("Sending %d chars to Claude for curation...", len(user_prompt))

    message = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=8000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    raw = message.content[0].text.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)

    try:
        digest = _try_parse(raw)
    except ValueError:
        log.warning("JSON parse failed - asking Claude to self-correct...")
        fix = client.messages.create(
            model="claude-opus-4-7",
            max_tokens=8000,
            messages=[{
                "role": "user",
                "content": f"Fix this JSON so it is valid. Return ONLY the corrected JSON, nothing else:\n\n{raw}"
            }],
        )
        raw2 = fix.content[0].text.strip()
        if raw2.startswith("```"):
            raw2 = re.sub(r"^```[a-z]*\n?", "", raw2)
            raw2 = re.sub(r"\n?```$", "", raw2)
        digest = _try_parse(raw2)

    log.info("Curated digest: %d sections", len(digest.get("sections", [])))
    return digest
