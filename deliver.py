"""
Delivery — sends a short WhatsApp/SMS/email with the digest link.
Never sends the full digest body, just the link.
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
    base = os.environ.get("PAGES_BASE_URL", config.PAGES_BASE_URL).rstrip("/")
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
    try:
        r = requests.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
            data={"From": from_, "To": to, "Body": body},
            auth=(sid, token),
            timeout=20,
        )
        d = r.json()
        if r.status_code in (200, 201):
            log.info("WhatsApp sent — SID: %s", d.get("sid"))
            return {"method": "whatsapp", "status": "sent", "sid": d.get("sid")}
        log.error("WhatsApp error: %s", d)
        return {"method": "whatsapp", "status": "failed", "error": d.get("message")}
    except Exception as e:
        return {"method": "whatsapp", "status": "error", "error": str(e)}


def _sms(link: str, date_str: str) -> dict:
    sid   = config.TWILIO_ACCOUNT_SID
    token = config.TWILIO_AUTH_TOKEN
    from_ = os.environ.get("TWILIO_SMS_FROM", "")
    to    = os.environ.get("RECIPIENT_PHONE", "")
    if not all([sid, token, from_, to]):
        return {"method": "sms", "status": "skipped",
                "reason": "Missing: TWILIO_SMS_FROM / RECIPIENT_PHONE"}
    try:
        r = requests.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
            data={"From": from_, "To": to, "Body": f"Morning Brief {date_str}: {link}"},
            auth=(sid, token), timeout=20,
        )
        d = r.json()
        if r.status_code in (200, 201):
            return {"method": "sms", "status": "sent", "sid": d.get("sid")}
        return {"method": "sms", "status": "failed", "error": d.get("message")}
    except Exception as e:
        return {"method": "sms", "status": "error", "error": str(e)}


def _email(link: str, date_str: str) -> dict:
    user = config.SMTP_USER
    pw   = config.SMTP_PASS
    to   = config.EMAIL_TO
    if not all([user, pw, to]):
        return {"method": "email", "status": "skipped",
                "reason": "Missing: SMTP_USER / SMTP_PASS / EMAIL_TO"}
    msg = EmailMessage()
    msg["Subject"] = f"Morning Global Brief — {date_str}"
    msg["From"]    = config.EMAIL_FROM or user
    msg["To"]      = to
    msg["Date"]    = formatdate(localtime=True)
    msg.set_content(
        f"Good morning, {config.RECIPIENT_NAME}!\n\n"
        f"Your Morning Global Brief for {date_str} is ready:\n{link}\n\n"
        f"Stay sharp.\n— The Brief"
    )
    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=30) as smtp:
            smtp.starttls(context=ctx)
            smtp.login(user, pw)
            smtp.send_message(msg)
        return {"method": "email", "status": "sent", "to": to}
    except Exception as e:
        return {"method": "email", "status": "error", "error": str(e)}


def deliver(date_str: str) -> list[dict]:
    link = _build_link(date_str)
    log.info("Digest link: %s", link)
    results = []
    for fn in (_whatsapp, _sms, _email):
        r = fn(link, date_str)
        results.append(r)
        if r["status"] == "sent":
            break
    return results


def delivery_summary(results: list[dict]) -> str:
    lines = []
    for r in results:
        m, s = r.get("method", "?").upper(), r.get("status", "?")
        if s == "sent":
            lines.append(f"  ✓ {m}: SENT {r.get('sid') or r.get('to', '')}")
        elif s == "skipped":
            lines.append(f"  – {m}: SKIPPED — {r.get('reason', '')}")
        else:
            lines.append(f"  ✗ {m}: {s.upper()} — {r.get('error', '')}")
    return "\n".join(lines)
