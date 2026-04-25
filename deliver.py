"""
Delivery module — sends a short message with the digest link.
Priority: WhatsApp (Twilio) → SMS (Twilio) → Email.
Never sends the full digest body — just the link.
"""
import logging
import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formatdate

import requests

import config

log = logging.getLogger(__name__)


def _build_link(date_str: str) -> str:
    """Build the GitHub Pages URL for today's digest."""
    base = os.environ.get("PAGES_BASE_URL", config.PAGES_BASE_URL).rstrip("/")
    if not base:
        return f"(set PAGES_BASE_URL — e.g. https://yourusername.github.io/morning-brief)"
    filename = f"morning-global-brief-{config.today_filename()}.html"
    return f"{base}/{filename}"


def _whatsapp(link: str, date_str: str) -> dict:
    sid   = config.TWILIO_ACCOUNT_SID
    token = config.TWILIO_AUTH_TOKEN
    from_ = config.TWILIO_WHATSAPP_FROM
    to    = config.RECIPIENT_WHATSAPP

    if not all([sid, token, to]):
        return {"method": "whatsapp", "status": "skipped",
                "reason": "Missing: TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / RECIPIENT_WHATSAPP"}

    body = (
        f"Good morning, {config.RECIPIENT_NAME}! ☀️\n\n"
        f"Your Morning Global Brief is ready:\n{link}\n\n"
        f"{date_str}"
    )
    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
    try:
        r = requests.post(
            url,
            data={"From": from_, "To": to, "Body": body},
            auth=(sid, token),
            timeout=20,
        )
        d = r.json()
        if r.status_code in (200, 201):
            log.info("WhatsApp sent — SID: %s", d.get("sid"))
            return {"method": "whatsapp", "status": "sent", "sid": d.get("sid")}
        log.error("WhatsApp API error: %s", d)
        return {"method": "whatsapp", "status": "failed", "error": d.get("message")}
    except Exception as e:
        return {"method": "whatsapp", "status": "error", "error": str(e)}


def _sms(link: str, date_str: str) -> dict:
    sid    = config.TWILIO_ACCOUNT_SID
    token  = config.TWILIO_AUTH_TOKEN
    from_  = os.environ.get("TWILIO_SMS_FROM", "")
    to     = os.environ.get("RECIPIENT_PHONE", "")

    if not all([sid, token, from_, to]):
        return {"method": "sms", "status": "skipped",
                "reason": "Missing: TWILIO_SMS_FROM / RECIPIENT_PHONE"}

    body = f"Morning Brief {date_str}: {link}"
    url  = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
    try:
        r = requests.post(url, data={"From": from_, "To": to, "Body": body},
                          auth=(sid, token), timeout=20)
        d = r.json()
        if r.status_code in (200, 201):
            log.info("SMS sent — SID: %s", d.get("sid"))
            return {"method": "sms", "status": "sent", "sid": d.get("sid")}
        return {"method": "sms", "status": "failed", "error": d.get("message")}
    except Exception as e:
        return {"method": "sms", "status": "error", "error": str(e)}


def _email(link: str, date_str: str, html_path: str | None = None) -> dict:
    host  = config.SMTP_HOST
    port  = config.SMTP_PORT
    user  = config.SMTP_USER
    pw    = config.SMTP_PASS
    to    = config.EMAIL_TO

    if not all([user, pw, to]):
        return {"method": "email", "status": "skipped",
                "reason": "Missing: SMTP_USER / SMTP_PASS / EMAIL_TO"}

    msg = EmailMessage()
    msg["Subject"] = f"Morning Global Brief — {date_str}"
    msg["From"]    = config.EMAIL_FROM or user
    msg["To"]      = to
    msg["Date"]    = formatdate(localtime=True)

    plain_fallback = (
        f"Good morning, {config.RECIPIENT_NAME}!\n\n"
        f"Your Morning Global Brief for {date_str} is ready:\n{link}\n\n"
        f"(The HTML version is also embedded in this email.)\n\n"
        f"— The Brief"
    )
    msg.set_content(plain_fallback)

    if html_path and os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            html_body = f.read()
        msg.add_alternative(html_body, subtype="html")
        log.info("HTML body attached: %d bytes", len(html_body))

    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP(host, port, timeout=30) as smtp:
            smtp.starttls(context=ctx)
            smtp.login(user, pw)
            smtp.send_message(msg)
        log.info("Email sent to %s", to)
        return {"method": "email", "status": "sent", "to": to}
    except Exception as e:
        log.error("Email error: %s", e)
        return {"method": "email", "status": "error", "error": str(e)}


def deliver(date_str: str, html_path: str | None = None) -> list[dict]:
    link = _build_link(date_str)
    log.info("Digest link: %s", link)

    results = []
    for fn in (_whatsapp, _sms, _email):
        if fn is _email:
            r = fn(link, date_str, html_path=html_path)
        else:
            r = fn(link, date_str)
        results.append(r)
        if r["status"] == "sent":
            break   # stop after first success
    return results


def delivery_summary(results: list[dict]) -> str:
    lines = []
    for r in results:
        m = r.get("method", "?").upper()
        s = r.get("status", "?")
        if s == "sent":
            extra = r.get("sid") or r.get("to") or ""
            lines.append(f"  ✓ {m}: SENT  {extra}")
        elif s == "skipped":
            lines.append(f"  – {m}: SKIPPED — {r.get('reason', '')}")
        else:
            lines.append(f"  ✗ {m}: {s.upper()} — {r.get('error', r.get('reason', ''))}")
    return "\n".join(lines)
