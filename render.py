"""
Renders the Jinja2 HTML template. HTML is the primary artifact.
"""
import logging
import os
from datetime import datetime, timezone

from jinja2 import Environment, FileSystemLoader, select_autoescape

import config

log = logging.getLogger(__name__)


def render_html(digest: dict, market_data: dict, date_str: str) -> str:
    env = Environment(
        loader=FileSystemLoader(config.TEMPLATE_DIR),
        autoescape=select_autoescape(["html"]),
    )
    template = env.get_template("digest.html.j2")
    sections = digest.get("sections", [])
    section_names = [s["name"] for s in sections if s.get("stories")]
    ctx = {
        "recipient_name": config.RECIPIENT_NAME,
        "edition_date":   date_str,
        "lead_headline":  digest.get("lead_headline", ""),
        "sections":       sections,
        "section_names":  section_names,
        "market_data":    market_data,
        "what_to_watch":  digest.get("what_to_watch", []),
        "editors_note":   digest.get("editors_note", ""),
        "generated_at":   datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }
    html = template.render(**ctx)
    log.info("HTML rendered: %d bytes", len(html))
    return html


def export_html(html: str, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    log.info("HTML written: %s (%d KB)", path, len(html) // 1024)


def build_output_paths(date_str: str) -> dict[str, str]:
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    base = f"morning-global-brief-{date_str}"
    return {
        "html": os.path.join(config.OUTPUT_DIR, f"{base}.html"),
        "json": os.path.join(config.OUTPUT_DIR, f"{base}-digest.json"),
    }
