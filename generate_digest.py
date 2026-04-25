#!/usr/bin/env python3
"""
Morning Global Brief — daily generation script.

Steps:
  1. Fetch RSS feeds
  2. Fetch market data
  3. Curate with Claude
  4. Render HTML
  5. Send link via WhatsApp / SMS / email

Usage:
  python generate_digest.py [--no-deliver]
"""
import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ── env ──
def _load_dotenv():
    p = Path(__file__).parent / ".env"
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            k = k.strip(); v = v.strip().strip('"').strip("'")
            if k not in os.environ:
                os.environ[k] = v

_load_dotenv()

import config
import fetch_news
import curate
import render
import deliver as deliver_mod

# ── logging ──
os.makedirs(config.LOG_DIR, exist_ok=True)
tag = datetime.now(timezone.utc).strftime("%Y-%m-%d")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(config.LOG_DIR, f"digest-{tag}.log"), encoding="utf-8"),
    ],
)
log = logging.getLogger("generate")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-deliver", action="store_true")
    args = ap.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        log.error("ANTHROPIC_API_KEY is not set.")
        sys.exit(1)

    date_str  = config.today_str()
    fname_dt  = config.today_filename()
    paths     = render.build_output_paths(fname_dt)

    log.info("═" * 55)
    log.info("Morning Global Brief · %s", date_str)
    log.info("═" * 55)

    # 1. Fetch RSS
    log.info("[1/5] Fetching RSS feeds…")
    t0 = time.time()
    articles = fetch_news.fetch_all_feeds(config.RSS_FEEDS)
    log.info("  → %d articles in %.1fs", len(articles), time.time() - t0)
    if not articles:
        log.error("No articles — check network / RSS sources.")
        sys.exit(1)

    # 2. Market data
    log.info("[2/5] Fetching market data…")
    market_data = fetch_news.fetch_market_data()
    log.info("  → %d instruments", len(market_data))

    # 3. Curate
    log.info("[3/5] Curating with Claude…")
    t0 = time.time()
    digest = curate.curate_digest(articles, date_str, config.SECTIONS, api_key)
    log.info("  → %d sections in %.1fs", len(digest.get("sections", [])), time.time() - t0)

    with open(paths["json"], "w", encoding="utf-8") as f:
        json.dump(digest, f, indent=2, ensure_ascii=False)

    # 4. Render HTML
    log.info("[4/5] Rendering HTML…")
    html = render.render_html(digest, market_data, date_str)
    render.export_html(html, paths["html"])

    # 5. Deliver
    if args.no_deliver:
        log.info("[5/5] Delivery skipped.")
        delivery_results = []
    else:
        log.info("[5/5] Sending digest…")
        delivery_results = deliver_mod.deliver(date_str, html_path=paths["html"])
        log.info("Delivery:\n%s", deliver_mod.delivery_summary(delivery_results))

    log.info("═" * 55)
    log.info("HTML: %s", paths["html"])
    sent = any(r.get("status") == "sent" for r in delivery_results)
    if delivery_results and not sent:
        log.warning("DELIVERY INCOMPLETE — configure credentials in .env")
    log.info("═" * 55)


if __name__ == "__main__":
    main()
