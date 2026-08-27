"""
enrichment.py
-------------
Module 3: Profile Enrichment

Builds the full mandatory-field record for every profile that PASSED
filtering. Contact email is never guessed -- "Not Found" if unavailable.
"""

from typing import List

from src.logger import get_logger

log = get_logger("enrichment")


def enrich_record(record: dict) -> dict:
    email = record.get("email_hint") or "Not Found"
    return {
        "influencer_name": record["name"],
        "handle": record["handle"],
        "platform": record["platform"],
        "profile_url": record["profile_url"],
        "follower_count": record["follower_count"],
        "engagement_rate": record["engagement_rate"],
        "category_niche": record["niche"],
        "content_themes": ", ".join(record["content_themes"]),
        "contact_email": email,
        "website": "Not Found",
        "audience_age": record.get("audience_age", "Not Found"),
        "audience_gender": record.get("audience_gender", "Not Found"),
        "audience_geography": record.get("geography", "Not Found"),
        "status": record["status"],
        "filter_reasons": record["filter_reasons"],
        "has_valid_email": email != "Not Found",
    }


def run_enrichment(classified_records: List[dict]) -> List[dict]:
    passed_only = [r for r in classified_records if r["status"] == "Passed"]
    enriched = [enrich_record(r) for r in passed_only]
    with_email = sum(1 for r in enriched if r["has_valid_email"])
    log.info(f"Enriched {len(enriched)} shortlisted profiles ({with_email} with valid email)")
    return enriched
