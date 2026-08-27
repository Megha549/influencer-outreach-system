"""
main.py
-------
Orchestrates: Discovery -> Filtering -> Enrichment -> Personalization ->
Sending -> Tracking, and writes all deliverable CSVs to /output.

Usage:
    python3 -m src.main --niche "Beauty & Fashion" --count 60 [--fresh]
"""

import argparse
import csv
import os
import sqlite3

from src import config
from src.discovery import run_discovery
from src.filtering import run_filtering
from src.enrichment import run_enrichment
from src.personalization import run_personalization
from src.sender import run_sending
from src.logger import get_logger

log = get_logger("main")


def write_csv(rows, path, fieldnames):
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "") for k in fieldnames})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--niche", default=config.DEFAULT_NICHE)
    parser.add_argument("--count", type=int, default=config.DEFAULT_DISCOVERY_COUNT)
    parser.add_argument("--fresh", action="store_true", help="Reset the outreach DB (clears dedupe history)")
    parser.add_argument("--kaggle-csv", default=None,
                         help="Path to a downloaded Kaggle influencer CSV (e.g. Top 1000 Instagram Influencers) "
                              "to use as a REAL data source, blended with simulated top-up to reach --count.")
    parser.add_argument("--kaggle-keywords", default="fashion,beauty",
                         help="Comma-separated keywords used to match the Kaggle CSV's category column to the niche.")
    parser.add_argument("--kaggle-max", type=int, default=None,
                         help="Max real Kaggle records to include (default: ~1/3 of --count). Public 'Top N' "
                              "datasets are mega-influencers who will mostly fail the micro-influencer filter, "
                              "so this cap leaves room for simulated micro-range profiles to carry the demo "
                              "through enrichment/personalization/sending.")
    args = parser.parse_args()

    os.makedirs(config.DATA_DIR, exist_ok=True)
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)

    if args.fresh and os.path.exists(config.DB_PATH):
        os.remove(config.DB_PATH)
        log.info("Fresh run: cleared outreach.db")

    log.info(f"=== 1. Discovery (niche={args.niche}, target n={args.count}) ===")
    kaggle_keywords = [k.strip() for k in args.kaggle_keywords.split(",") if k.strip()] if args.kaggle_csv else None
    raw = run_discovery(niche=args.niche, min_count=args.count,
                         kaggle_csv_path=args.kaggle_csv, kaggle_niche_keywords=kaggle_keywords,
                         kaggle_max=args.kaggle_max)

    log.info("=== 2. Filtering & Classification ===")
    classified = run_filtering(raw, target_niche=args.niche)

    log.info("=== 3. Profile Enrichment ===")
    enriched = run_enrichment(classified)

    log.info("=== 4. AI Personalization ===")
    messages = run_personalization(enriched)

    log.info("=== 5. Sending Layer ===")
    tracker_rows = run_sending(enriched, messages)

    log.info("=== 6. Writing deliverables to /output ===")

    dataset_rows = [{
        "Name": r["name"], "Platform": r["platform"], "Followers": r["follower_count"],
        "Engagement Rate": f"{r['engagement_rate']:.2%}", "Niche": r["niche"],
        "Email": r.get("email_hint") or "Not Found", "Profile URL": r["profile_url"],
        "Content Theme": ", ".join(r["content_themes"]), "Status": r["status"],
        "Reasons": r["filter_reasons"], "Data Source": r.get("source", "unknown"),
    } for r in classified]
    write_csv(dataset_rows, os.path.join(config.OUTPUT_DIR, "influencer_dataset.csv"),
              ["Name", "Platform", "Followers", "Engagement Rate", "Niche", "Email",
               "Profile URL", "Content Theme", "Status", "Reasons", "Data Source"])

    enriched_rows = [{
        "Name": e["influencer_name"], "Platform": e["platform"], "Profile URL": e["profile_url"],
        "Followers": e["follower_count"], "Engagement Rate": f"{e['engagement_rate']:.2%}",
        "Niche": e["category_niche"], "Content Themes": e["content_themes"],
        "Contact Email": e["contact_email"], "Website": e["website"],
        "Audience Age": e["audience_age"], "Audience Gender": e["audience_gender"],
        "Audience Geography": e["audience_geography"],
    } for e in enriched]
    write_csv(enriched_rows, os.path.join(config.OUTPUT_DIR, "shortlisted_enriched.csv"),
              ["Name", "Platform", "Profile URL", "Followers", "Engagement Rate", "Niche",
               "Content Themes", "Contact Email", "Website", "Audience Age", "Audience Gender",
               "Audience Geography"])

    msg_rows = [{
        "Name": m["influencer_name"], "Platform": m["platform"], "Contact Email": m["contact_email"],
        "Email Pitch": m["email_pitch"] or "(skipped - no valid email)", "Instagram DM": m["instagram_dm"],
    } for m in messages]
    write_csv(msg_rows, os.path.join(config.OUTPUT_DIR, "personalized_messages.csv"),
              ["Name", "Platform", "Contact Email", "Email Pitch", "Instagram DM"])

    write_csv(tracker_rows, os.path.join(config.OUTPUT_DIR, "outreach_tracker.csv"),
              ["influencer_name", "email", "message_generated", "sent_date", "status", "instagram_dm_status"])

    # Also export the full DB table for transparency/audit
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    db_rows = [dict(r) for r in conn.execute("SELECT * FROM outreach_log").fetchall()]
    conn.close()
    if db_rows:
        write_csv(db_rows, os.path.join(config.OUTPUT_DIR, "outreach_db_export.csv"), list(db_rows[0].keys()))

    log.info("Done. Deliverables written to /output:")
    for fname in ["influencer_dataset.csv", "shortlisted_enriched.csv",
                  "personalized_messages.csv", "outreach_tracker.csv", "outreach_db_export.csv"]:
        log.info(f"  - {fname}")


if __name__ == "__main__":
    main()
