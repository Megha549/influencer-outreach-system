"""
personalization.py
-------------------
Module 4: AI Message Personalization

Two backends behind one interface:
    - ClaudeGenerator: real Anthropic Messages API call (used automatically
      if ANTHROPIC_API_KEY is set).
    - RuleBasedGenerator: dynamic, signal-driven fallback (used when no key
      is available, e.g. this sandbox) -- draws from large phrasing pools
      so messages are genuinely different per influencer, not one template.
"""

import json
import random
import re
from typing import Tuple

from src import config
from src.logger import get_logger

log = get_logger("personalization")
random.seed(7)

COLLAB_ANGLES = [
    "an affiliate campaign with a bespoke discount code",
    "a paid UGC content package",
    "our brand ambassador program",
    "a barter collaboration with our latest product line",
    "a sponsored content placement",
    "a limited-run co-branded capsule",
    "a giveaway collaboration for your audience",
]
VALUE_PROPS = [
    "a commission structure that scales with performance",
    "full creative freedom over how you present it",
    "early access to our new product drop",
    "a flat sponsorship fee plus usage rights bonus",
    "long-term partnership potential beyond a single post",
    "a dedicated affiliate link with real-time tracking",
]
OPENERS = [
    "Hi {name}, I've been following your {theme} content",
    "Hi {name}, your recent {theme} posts caught our eye",
    "Hey {name}, loved your take on {theme}",
    "Hi {name}, your {theme} content has such a distinct style",
    "Hey {name}, we came across your {theme} posts and were impressed",
]
DM_OPENERS = [
    "Hi {name}, loved your {theme} content!",
    "Hey {name}, your {theme} posts are great!",
    "Hi {name}! Really enjoyed your recent {theme}.",
    "Hey {name}, your {theme} content stood out to us!",
]
CLOSERS = [
    "Would you be open to a quick chat this week to explore details and see if it's a fit for your content calendar?",
    "Let me know if you'd like to hear more -- happy to share full details whenever works for you.",
    "Would love to hop on a short call to walk through the specifics if you're interested.",
]


def _first_theme(themes_str: str) -> str:
    return themes_str.split(",")[0].strip()


def _trim_to_word_range(text: str, min_words: int, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    trimmed = " ".join(words[:max_words])
    if not trimmed.endswith((".", "!", "?")):
        trimmed = trimmed.rstrip(",;") + "."
    return trimmed


class RuleBasedGenerator:
    def generate(self, profile: dict) -> Tuple[str, str]:
        name = profile["influencer_name"]
        niche = profile["category_niche"]
        theme = _first_theme(profile["content_themes"])
        followers = profile["follower_count"]
        angle = random.choice(COLLAB_ANGLES)
        value = random.choice(VALUE_PROPS)
        closer = random.choice(CLOSERS)
        tier = "growing" if followers < 20000 else ("established" if followers < 60000 else "high-reach")

        opener = random.choice(OPENERS).format(name=name, theme=theme)
        email = (
            f"{opener}, and think your {tier} {niche.lower()} audience would be a great fit for our brand. "
            f"We'd love to explore {angle} together -- we can offer {value}. "
            f"Your style feels authentic and aligned with what we're building, and we think your followers would "
            f"genuinely connect with the product. {closer}"
        )
        email = _trim_to_word_range(email, config.EMAIL_MIN_WORDS, config.EMAIL_MAX_WORDS)

        dm_opener = random.choice(DM_OPENERS).format(name=name, theme=theme)
        dm = f"{dm_opener} Your {niche.lower()} audience feels like a great fit for a collab -- interested?"
        dm = _trim_to_word_range(dm, config.DM_MIN_WORDS, config.DM_MAX_WORDS)

        return email, dm


class ClaudeGenerator:
    """Real LLM-backed generator. Requires ANTHROPIC_API_KEY."""

    def __init__(self):
        import anthropic
        self.client = anthropic.Anthropic()
        self.model = config.CLAUDE_MODEL

    def generate(self, profile: dict) -> Tuple[str, str]:
        prompt = f"""You are writing brand-outreach messages to a micro-influencer for a collaboration.

Influencer profile:
- Name: {profile['influencer_name']}
- Platform: {profile['platform']}
- Niche: {profile['category_niche']}
- Content themes: {profile['content_themes']}
- Followers: {profile['follower_count']}
- Engagement rate: {profile['engagement_rate']:.2%}

Write TWO outreach messages personalized to this specific profile (reference
their niche/content naturally, propose a concrete collaboration angle, state
a value proposition):
1. EMAIL: a collaboration pitch, {config.EMAIL_MIN_WORDS}-{config.EMAIL_MAX_WORDS} words.
2. DM: an Instagram DM, {config.DM_MIN_WORDS}-{config.DM_MAX_WORDS} words, short and natural.

Respond ONLY as JSON: {{"email": "...", "dm": "..."}}"""

        resp = self.client.messages.create(
            model=self.model, max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(b.text for b in resp.content if hasattr(b, "text"))
        text = re.sub(r"^```json|```$", "", text.strip()).strip()
        data = json.loads(text)
        return data["email"], data["dm"]


def get_generator():
    if config.ANTHROPIC_API_KEY:
        try:
            gen = ClaudeGenerator()
            log.info("Personalization backend: ClaudeGenerator (real LLM)")
            return gen
        except Exception as e:
            log.warning(f"ClaudeGenerator init failed ({e}); falling back to RuleBasedGenerator")
    log.info("Personalization backend: RuleBasedGenerator (offline fallback)")
    return RuleBasedGenerator()


def run_personalization(enriched_records: list) -> list:
    generator = get_generator()
    backend_name = generator.__class__.__name__
    results = []
    for profile in enriched_records:
        try:
            if not profile["has_valid_email"]:
                _, dm = generator.generate(profile)
                email_pitch = None
            else:
                email_pitch, dm = generator.generate(profile)
        except Exception as e:
            log.error(f"Generation failed for {profile['influencer_name']}: {e}")
            email_pitch, dm = None, None

        results.append({
            "influencer_name": profile["influencer_name"],
            "platform": profile["platform"],
            "contact_email": profile["contact_email"],
            "email_pitch": email_pitch,
            "instagram_dm": dm,
            "generator_backend": backend_name,
        })
    log.info(f"Generated messages for {len(results)} profiles via {backend_name}")
    return results
