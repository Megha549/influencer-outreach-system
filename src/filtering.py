"""
filtering.py
------------
Module 2: Filtering & Classification

Implemented category: "Fashion & Beauty influencers" (matches the
assignment's own worked example). Hard criteria: niche match, follower
range, engagement rate floor. Soft (non-blocking) criterion: geography.
Every record -- passed or failed -- gets a human-readable reason string.
"""

from typing import Dict, List

from src import config
from src.logger import get_logger

log = get_logger("filtering")


def compute_engagement_rate(record: dict) -> float:
    followers = record["follower_count"]
    if followers <= 0:
        return 0.0
    return round((record["avg_likes"] + record["avg_comments"]) / followers, 4)


def classify(record: dict, target_niche: str) -> Dict:
    passed_reasons, failed_reasons = [], []
    er = compute_engagement_rate(record)
    record["engagement_rate"] = er

    if record["niche"] == target_niche:
        passed_reasons.append(f"Niche matches target ({target_niche})")
    else:
        failed_reasons.append(f"Niche '{record['niche']}' != target '{target_niche}'")

    if config.MIN_FOLLOWERS <= record["follower_count"] <= config.MAX_FOLLOWERS:
        passed_reasons.append(f"Follower count {record['follower_count']:,} within micro-influencer range")
    else:
        failed_reasons.append(
            f"Follower count {record['follower_count']:,} outside "
            f"{config.MIN_FOLLOWERS:,}-{config.MAX_FOLLOWERS:,} range"
        )

    if er >= config.MIN_ENGAGEMENT_RATE:
        passed_reasons.append(f"Engagement rate {er:.2%} >= {config.MIN_ENGAGEMENT_RATE:.0%} threshold")
    else:
        failed_reasons.append(f"Engagement rate {er:.2%} below {config.MIN_ENGAGEMENT_RATE:.0%} threshold")

    geo_ok = record["geography"] in config.TARGET_GEOGRAPHIES
    geo_note = (
        f"Geography '{record['geography']}' in target markets" if geo_ok
        else f"Geography '{record['geography']}' outside primary target markets (soft flag, non-blocking)"
    )

    record["status"] = "Passed" if not failed_reasons else "Failed"
    record["filter_reasons"] = "; ".join(passed_reasons + failed_reasons + [geo_note])
    return record


def run_filtering(raw_records: List[dict], target_niche: str = config.DEFAULT_NICHE) -> List[dict]:
    classified = [classify(r, target_niche) for r in raw_records]
    passed = sum(1 for r in classified if r["status"] == "Passed")
    log.info(f"Classified {len(classified)} profiles -> Passed: {passed}, Failed: {len(classified) - passed}")
    return classified
