"""
Uses Claude to curate raw RSS articles into a structured editorial digest.
"""
import json
import re
import logging
from typing import Any

import anthropic

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
- Be honest about what you know. Do not invent facts. Stick to what the articles say.
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


def curate_digest(articles: list[dict], date_str: str, sections: list[str], api_key: str) -> dict[str, Any]:
    client = anthropic.Anthropic(api_key=api_key)
    articles_text = articles_to_text(articles)
    user_prompt = USER_PROMPT_TEMPLATE.format(
        date=date_str,
        sections=", ".join(s for s in sections if s != "Markets at a Glance"),
        articles_text=articles_text,
    )
    log.info("Sending %d chars to Claude for curation…", len(user_prompt))
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
        digest = json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if m:
            digest = json.loads(m.group(0))
        else:
            raise
    log.info("Curated digest: %d sections", len(digest.get("sections", [])))
    return digest
