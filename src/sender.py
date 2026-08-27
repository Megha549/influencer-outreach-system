"""
sender.py
---------
Module 5: Sending Layer + Tracking (SQLite-backed)

Why SQLite instead of a JSON set + CSV log (v1 approach): a real
production system needs queryable, ACID-safe persistent storage for
dedupe and audit history -- SQLite gives that with zero extra
infrastructure, and the schema below is a straight upgrade path to
Postgres at scale (see README §Scalability).

Requirements covered:
    1. Select influencers with a valid contact email.
    2. Retrieve their personalized email message.
    3. Send or simulate sending the email.
    4. Record the sending status.
    5. Prevent duplicate outreach (UNIQUE constraint + pre-check on email).
    6. Maintain a basic outreach log (outreach_log table, queryable).

Instagram DMs are never auto-sent (no bypassing platform restrictions);
they're logged as "Ready for manual/authorized send".
"""

import smtplib
import sqlite3
from datetime import datetime, timezone
from email.mime.text import MIMEText
from typing import List

from src import config
from src.logger import get_logger

log = get_logger("sender")

SCHEMA = """
CREATE TABLE IF NOT EXISTS outreach_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    influencer_name TEXT NOT NULL,
    email TEXT NOT NULL,
    message_generated TEXT NOT NULL,
    sent_date TEXT,
    status TEXT NOT NULL,
    instagram_dm_status TEXT,
    UNIQUE(email)
);
"""


def get_connection(db_path: str = config.DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute(SCHEMA)
    conn.commit()
    return conn


class SimulatedSender:
    def send_email(self, to_email: str, subject: str, body: str) -> bool:
        return True  # stand-in for a real network call


class SMTPSender:
    def send_email(self, to_email: str, subject: str, body: str) -> bool:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = config.SMTP_USER
        msg["To"] = to_email
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as server:
            server.starttls()
            server.login(config.SMTP_USER, config.SMTP_PASS)
            server.send_message(msg)
        return True


def get_sender():
    if config.SMTP_HOST and config.SMTP_USER and config.SMTP_PASS:
        log.info("Sending backend: SMTPSender (real)")
        return SMTPSender()
    log.info("Sending backend: SimulatedSender (offline fallback)")
    return SimulatedSender()


def already_contacted(conn: sqlite3.Connection, email: str) -> bool:
    cur = conn.execute("SELECT 1 FROM outreach_log WHERE email = ? AND status = 'Sent'", (email,))
    return cur.fetchone() is not None


def log_outcome(conn: sqlite3.Connection, row: dict):
    conn.execute(
        """INSERT INTO outreach_log (influencer_name, email, message_generated, sent_date, status, instagram_dm_status)
           VALUES (:influencer_name, :email, :message_generated, :sent_date, :status, :instagram_dm_status)
           ON CONFLICT(email) DO UPDATE SET
             influencer_name=excluded.influencer_name, message_generated=excluded.message_generated,
             sent_date=excluded.sent_date, status=excluded.status, instagram_dm_status=excluded.instagram_dm_status
           WHERE outreach_log.status != 'Sent'""",  # never overwrite a prior successful send
        row,
    )
    conn.commit()


def run_sending(enriched_records: List[dict], messages: List[dict], db_path: str = config.DB_PATH) -> List[dict]:
    enriched_by_name = {r["influencer_name"]: r for r in enriched_records}
    conn = get_connection(db_path)
    sender = get_sender()
    now = datetime.now(timezone.utc).isoformat()

    results = []
    for m in messages:
        name = m["influencer_name"]
        email = m["contact_email"]
        profile = enriched_by_name.get(name, {})

        if email == "Not Found" or not email:
            row = {"influencer_name": name, "email": email or "unknown", "message_generated": "No",
                   "sent_date": "", "status": "Skipped - No valid email", "instagram_dm_status": ""}
            results.append(row)
            continue

        if already_contacted(conn, email):
            row = {"influencer_name": name, "email": email, "message_generated": "Yes",
                   "sent_date": "", "status": "Skipped - Duplicate (already contacted)",
                   "instagram_dm_status": "Ready for manual/authorized send"}
            results.append(row)
            continue

        subject = f"Collaboration opportunity with {profile.get('category_niche', 'your')} content"
        try:
            ok = sender.send_email(email, subject, m["email_pitch"])
            status = "Sent" if ok else "Failed"
        except Exception as e:
            log.error(f"Send failed for {email}: {e}")
            status = f"Failed - {e}"

        row = {"influencer_name": name, "email": email, "message_generated": "Yes",
               "sent_date": now if status == "Sent" else "", "status": status,
               "instagram_dm_status": "Ready for manual/authorized send"}
        results.append(row)
        log_outcome(conn, row)

    conn.close()
    sent = sum(1 for r in results if r["status"] == "Sent")
    log.info(f"Processed {len(results)} outreach candidates -> Sent: {sent}, Other: {len(results) - sent}")
    return results
