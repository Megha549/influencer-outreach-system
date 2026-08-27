"""
tests/test_pipeline.py
-----------------------
Basic unit tests for the filtering, enrichment, and word-count logic.
Run with: python3 -m pytest tests/ -v   (or: python3 -m unittest discover)
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.filtering import classify, compute_engagement_rate
from src.enrichment import enrich_record
from src.personalization import _trim_to_word_range


def make_record(**overrides):
    base = {
        "name": "TestUser", "handle": "@test.glow", "platform": "Instagram",
        "profile_url": "https://instagram.com/test.glow", "follower_count": 20000,
        "avg_likes": 900, "avg_comments": 40, "niche": "Beauty & Fashion",
        "content_themes": ["skincare routines", "makeup tutorials"], "geography": "US",
        "audience_age": "18-24", "audience_gender": "70% Female",
        "bio": "test bio", "email_hint": "test@gmail.com",
    }
    base.update(overrides)
    return base


class TestEngagementRate(unittest.TestCase):
    def test_normal_case(self):
        r = make_record(follower_count=10000, avg_likes=400, avg_comments=100)
        self.assertAlmostEqual(compute_engagement_rate(r), 0.05)

    def test_zero_followers_does_not_crash(self):
        r = make_record(follower_count=0, avg_likes=0, avg_comments=0)
        self.assertEqual(compute_engagement_rate(r), 0.0)


class TestFiltering(unittest.TestCase):
    def test_passes_all_criteria(self):
        r = make_record(follower_count=20000, avg_likes=900, avg_comments=100, niche="Beauty & Fashion")
        result = classify(r, "Beauty & Fashion")
        self.assertEqual(result["status"], "Passed")

    def test_fails_on_niche_mismatch(self):
        r = make_record(niche="Gaming")
        result = classify(r, "Beauty & Fashion")
        self.assertEqual(result["status"], "Failed")
        self.assertIn("Niche", result["filter_reasons"])

    def test_fails_on_follower_count_too_low(self):
        r = make_record(follower_count=2000)
        result = classify(r, "Beauty & Fashion")
        self.assertEqual(result["status"], "Failed")

    def test_fails_on_follower_count_too_high(self):
        r = make_record(follower_count=500000)
        result = classify(r, "Beauty & Fashion")
        self.assertEqual(result["status"], "Failed")

    def test_fails_on_low_engagement(self):
        r = make_record(follower_count=50000, avg_likes=100, avg_comments=10)
        result = classify(r, "Beauty & Fashion")
        self.assertEqual(result["status"], "Failed")
        self.assertIn("Engagement rate", result["filter_reasons"])

    def test_reasons_always_populated(self):
        r = make_record()
        result = classify(r, "Beauty & Fashion")
        self.assertTrue(len(result["filter_reasons"]) > 0)


class TestEnrichment(unittest.TestCase):
    def test_missing_email_marked_not_found(self):
        r = make_record(email_hint=None)
        r["status"] = "Passed"
        r["filter_reasons"] = "ok"
        r["engagement_rate"] = 0.05
        enriched = enrich_record(r)
        self.assertEqual(enriched["contact_email"], "Not Found")
        self.assertFalse(enriched["has_valid_email"])

    def test_present_email_kept(self):
        r = make_record(email_hint="found@gmail.com")
        r["status"] = "Passed"
        r["filter_reasons"] = "ok"
        r["engagement_rate"] = 0.05
        enriched = enrich_record(r)
        self.assertEqual(enriched["contact_email"], "found@gmail.com")
        self.assertTrue(enriched["has_valid_email"])

    def test_mandatory_fields_present(self):
        r = make_record()
        r["status"] = "Passed"
        r["filter_reasons"] = "ok"
        r["engagement_rate"] = 0.05
        enriched = enrich_record(r)
        for field in ["influencer_name", "platform", "profile_url", "follower_count",
                      "engagement_rate", "category_niche", "content_themes", "contact_email"]:
            self.assertIn(field, enriched)


class TestMessageWordLimits(unittest.TestCase):
    def test_trims_over_max(self):
        text = " ".join(["word"] * 100) + "."
        trimmed = _trim_to_word_range(text, 60, 90)
        self.assertLessEqual(len(trimmed.split()), 90)

    def test_leaves_within_range_untouched(self):
        text = " ".join(["word"] * 70)
        trimmed = _trim_to_word_range(text, 60, 90)
        self.assertEqual(trimmed, text)


if __name__ == "__main__":
    unittest.main()
