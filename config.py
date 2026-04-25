"""
Daily News Digest - Configuration
"""
import os
from datetime import datetime
import pytz

# ─── Recipient ────────────────────────────────────────────────────────────────
RECIPIENT_NAME = "Urvil"
RECIPIENT_TIMEZONE = "Asia/Dubai"   # UAE Standard Time (GMT+4)
DIGEST_HOUR = 7                     # 7:00 AM local time

# ─── Delivery ─────────────────────────────────────────────────────────────────
# WhatsApp via Twilio (preferred)
TWILIO_ACCOUNT_SID  = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN   = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_WHATSAPP_FROM = os.environ.get("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")  # Twilio sandbox
RECIPIENT_WHATSAPP  = os.environ.get("RECIPIENT_WHATSAPP", "whatsapp:+35796728544")

# Email fallback
SMTP_HOST    = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT    = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER    = os.environ.get("SMTP_USER", "")
SMTP_PASS    = os.environ.get("SMTP_PASS", "")
EMAIL_FROM   = os.environ.get("EMAIL_FROM", SMTP_USER)
EMAIL_TO     = os.environ.get("EMAIL_TO", "")

# File hosting for PDF link (optional - for SMS/WhatsApp link delivery)
PAGES_BASE_URL = os.environ.get("PAGES_BASE_URL", "https://yuv91292.github.io/morning-brief")

# ─── APIs ─────────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
NEWS_API_KEY      = os.environ.get("NEWS_API_KEY", "")           # newsapi.org (optional)

# ─── Output ───────────────────────────────────────────────────────────────────
OUTPUT_DIR   = os.path.join(os.path.dirname(__file__), "output")
LOG_DIR      = os.path.join(os.path.dirname(__file__), "logs")
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")

# ─── RSS Feed Sources ──────────────────────────────────────────────────────────
RSS_FEEDS = {
    "Reuters World":       "https://feeds.reuters.com/reuters/topNews",
    "BBC World":           "https://feeds.bbci.co.uk/news/world/rss.xml",
    "BBC Business":        "https://feeds.bbci.co.uk/news/business/rss.xml",
    "BBC Technology":      "https://feeds.bbci.co.uk/news/technology/rss.xml",
    "AP Top News":         "https://apnews.com/rss/apf-topnews",
    "Guardian World":      "https://www.theguardian.com/world/rss",
    "Guardian Business":   "https://www.theguardian.com/business/rss",
    "Guardian Tech":       "https://www.theguardian.com/uk/technology/rss",
    "Al Jazeera":          "https://www.aljazeera.com/xml/rss/all.xml",
    "CNN Top Stories":     "http://rss.cnn.com/rss/cnn_topstories.rss",
    "NYT World":           "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
    "NYT Business":        "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml",
    "NYT Technology":      "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
    "Economist":           "https://www.economist.com/the-world-this-week/rss.xml",
    "FT":                  "https://www.ft.com/rss/home/uk",
    "Bloomberg Markets":   "https://feeds.bloomberg.com/markets/news.rss",
    "Nikkei Asia":         "https://asia.nikkei.com/rss/feed/nar",
    "Times of India":      "https://timesofindia.indiatimes.com/rssfeeds/296589292.cms",
    "Khaleej Times":       "https://www.khaleejtimes.com/rss",
    "Gulf News":           "https://gulfnews.com/rss",
    "BBC Sport":           "https://feeds.bbci.co.uk/sport/rss.xml",
    "Guardian Sport":      "https://www.theguardian.com/uk/sport/rss",
    "ESPN Top":            "https://www.espn.com/espn/rss/news",
    "BBC Entertainment":   "https://feeds.bbci.co.uk/news/entertainment_and_arts/rss.xml",
    "Variety":             "https://variety.com/feed/",
    "Guardian Lifestyle":  "https://www.theguardian.com/lifeandstyle/rss",
}

# Sections and their editorial mapping
SECTIONS = [
    "Front Page",
    "World & Geopolitics",
    "Business & Markets",
    "Technology & AI",
    "Climate & Energy",
    "India / UAE / US Watch",
    "Sport, Culture & Lifestyle",
    "Markets at a Glance",
    "What to Watch Next",
]

def today_str():
    tz = pytz.timezone(RECIPIENT_TIMEZONE)
    return datetime.now(tz).strftime("%A, %B %-d, %Y")

def today_filename():
    tz = pytz.timezone(RECIPIENT_TIMEZONE)
    return datetime.now(tz).strftime("%Y-%m-%d")
