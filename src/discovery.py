"""
discovery.py
------------
Module 1: Influencer Discovery

Design: discovery blends up to three sources -- a real Kaggle dataset CSV
(if --kaggle-csv is given), the live YouTube Data API (if YOUTUBE_API_KEY
is set), and a simulated provider that tops up the pool to the requested
count. Every record carries a "source" tag ("kaggle_real_dataset" /
"youtube_data_api_v3" / "simulated_directory") so real and synthetic data
are never ambiguous downstream. See README section 3 for full details.
"""

import random
from dataclasses import dataclass, asdict
from typing import List, Optional

from src import config
from src.logger import get_logger

log = get_logger("discovery")
random.seed(config.RANDOM_SEED)

PLATFORMS = ["Instagram", "YouTube", "TikTok"]
NICHES = ["Beauty & Fashion", "Fitness", "Fintech", "Crypto", "Parenting", "Gaming", "Lifestyle", "Technology"]
GEOGRAPHIES = ["US", "UK", "India", "Canada", "Australia", "Germany", "UAE", "Philippines"]
FIRST_NAMES = [
    "Sarah", "Maya", "Priya", "Ava", "Zara", "Elena", "Chloe", "Nina",
    "James", "Ryan", "Liam", "Noah", "Kabir", "Diego", "Omar", "Leo",
    "Isla", "Freya", "Amara", "Layla", "Sofia", "Grace", "Ella", "Ruby",
]
HANDLE_WORDS = ["glow", "edit", "diaries", "vibes", "studio", "co", "life", "daily", "curated", "loop", "lab", "notes"]

BEAUTY_THEMES = [
    "skincare routines", "clean beauty product reviews", "GRWM (get ready with me)",
    "makeup tutorials", "sustainable fashion hauls", "seasonal outfit lookbooks",
    "drugstore beauty dupes", "capsule wardrobe styling",
]
OTHER_THEMES = {
    "Fitness": ["home workout routines", "strength training tips", "marathon training vlogs", "mobility & recovery"],
    "Fintech": ["personal budgeting tips", "investing 101 explainers", "credit score hacks"],
    "Crypto": ["market breakdown threads", "DeFi explainers", "NFT project reviews"],
    "Parenting": ["toddler routines", "meal prep for kids", "postpartum life updates"],
    "Gaming": ["let's-play streams", "game review shorts", "speedrun highlights"],
    "Lifestyle": ["day-in-the-life vlogs", "home organization", "travel diaries"],
    "Technology": ["gadget unboxings", "app review shorts", "productivity setups"],
}
CONTACT_DOMAINS = ["gmail.com", "outlook.com", "creatormail.com", "talent-mgmt.co"]


@dataclass
class RawInfluencer:
    name: str
    handle: str
    platform: str
    profile_url: str
    follower_count: int
    avg_likes: int
    avg_comments: int
    niche: str
    content_themes: List[str]
    geography: str
    audience_age: str
    audience_gender: str
    bio: str
    email_hint: Optional[str] = None
    source: str = "simulated_directory"


class DiscoveryProvider:
    def discover(self, niche: str, min_count: int) -> List[RawInfluencer]:
        raise NotImplementedError


class SimulatedDirectoryProvider(DiscoveryProvider):
    """Default provider: realistic synthetic profiles (see README §3)."""

    def _handle(self, name: str) -> str:
        return f"@{name.lower()}.{random.choice(HANDLE_WORDS)}"

    def _profile_url(self, platform: str, handle: str) -> str:
        h = handle.lstrip("@")
        return {
            "Instagram": f"https://instagram.com/{h}",
            "YouTube": f"https://youtube.com/@{h}",
            "TikTok": f"https://tiktok.com/@{h}",
        }[platform]

    def _themes_for(self, niche: str) -> List[str]:
        pool = BEAUTY_THEMES if niche == "Beauty & Fashion" else OTHER_THEMES.get(niche, ["general content"])
        return random.sample(pool, k=min(2, len(pool)))

    def discover(self, niche: Optional[str], min_count: int) -> List[RawInfluencer]:
        results = []
        for i in range(min_count):
            chosen_niche = niche if (niche and random.random() < 0.55) else random.choice(NICHES)
            name = random.choice(FIRST_NAMES)
            platform = random.choice(PLATFORMS)
            handle = self._handle(name)
            followers = int(random.triangular(4000, 100000, 20000))

            base_er = {"Instagram": 0.035, "YouTube": 0.045, "TikTok": 0.06}[platform]
            noise = random.uniform(-0.02, 0.02)
            size_penalty = (followers / 100000) * 0.015
            er = max(0.002, base_er - size_penalty + noise)
            avg_likes = int(followers * er * random.uniform(0.7, 0.9))
            avg_comments = int(avg_likes * random.uniform(0.02, 0.08))

            has_email = random.random() < 0.72
            email_hint = f"{name.lower()}.collabs@{random.choice(CONTACT_DOMAINS)}" if has_email else None

            results.append(RawInfluencer(
                name=name, handle=handle, platform=platform,
                profile_url=self._profile_url(platform, handle),
                follower_count=followers, avg_likes=avg_likes, avg_comments=avg_comments,
                niche=chosen_niche, content_themes=self._themes_for(chosen_niche),
                geography=random.choice(GEOGRAPHIES),
                audience_age=random.choice(["18-24", "18-24", "25-34", "25-34", "35-44"]),
                audience_gender=random.choice(["70% Female", "60% Female", "55% Male", "Balanced"]),
                bio=f"{chosen_niche} creator sharing {', '.join(self._themes_for(chosen_niche))}.",
                email_hint=email_hint,
            ))
        return results


class YouTubeDataAPIProvider(DiscoveryProvider):
    """
    Real, ToS-compliant discovery source using the public YouTube Data API v3.
    Requires YOUTUBE_API_KEY (free tier: https://console.cloud.google.com).

    Flow:
        1. search.list  -> find channels matching niche keywords
        2. channels.list -> pull real statistics (subscriberCount, viewCount,
           videoCount) for each channel found
        3. Map into RawInfluencer records. Engagement rate is estimated from
           (average views per recent video / subscribers) since the public
           API does not expose likes/comments at the channel level without
           per-video calls (kept out here to conserve API quota).

    Contact email: YouTube's public API does not expose creator emails.
    Per assignment rules ("never guess"), email_hint is left as None here;
    enrichment.py will correctly mark these as "Not Found" downstream.
    """

    BASE_URL = "https://www.googleapis.com/youtube/v3"

    # Search keywords per niche -- used to find relevant channels
    NICHE_KEYWORDS = {
        "Beauty & Fashion": ["beauty tips", "skincare routine", "makeup tutorial", "fashion haul"],
        "Fitness": ["home workout", "fitness routine", "strength training"],
        "Fintech": ["personal finance tips", "budgeting for beginners"],
        "Crypto": ["crypto explained", "blockchain basics"],
        "Parenting": ["parenting tips", "mom life vlog"],
        "Gaming": ["gaming channel", "let's play"],
        "Lifestyle": ["daily vlog", "lifestyle channel"],
        "Technology": ["tech review", "gadget unboxing"],
    }

    def __init__(self):
        import requests
        self.requests = requests
        self.api_key = config.YOUTUBE_API_KEY

    def _search_channel_ids(self, keyword: str, max_results: int) -> List[str]:
        resp = self.requests.get(
            f"{self.BASE_URL}/search",
            params={
                "part": "snippet", "q": keyword, "type": "channel",
                "maxResults": min(max_results, 50), "key": self.api_key,
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        return [item["snippet"]["channelId"] for item in data.get("items", [])]

    def _channel_stats(self, channel_ids: List[str]) -> List[dict]:
        if not channel_ids:
            return []
        resp = self.requests.get(
            f"{self.BASE_URL}/channels",
            params={
                "part": "snippet,statistics", "id": ",".join(channel_ids[:50]),
                "key": self.api_key,
            },
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json().get("items", [])

    def discover(self, niche: Optional[str], min_count: int) -> List[RawInfluencer]:
        keywords = self.NICHE_KEYWORDS.get(niche, [niche or "influencer"])
        seen_ids = set()
        channel_ids = []
        for kw in keywords:
            if len(channel_ids) >= min_count:
                break
            for cid in self._search_channel_ids(kw, max_results=min_count):
                if cid not in seen_ids:
                    seen_ids.add(cid)
                    channel_ids.append(cid)

        raw_channels = self._channel_stats(channel_ids)
        results = []
        for ch in raw_channels:
            stats = ch.get("statistics", {})
            snippet = ch.get("snippet", {})
            subs = int(stats.get("subscriberCount", 0)) if not stats.get("hiddenSubscriberCount") else 0
            views = int(stats.get("viewCount", 0))
            video_count = max(int(stats.get("videoCount", 1)), 1)

            if subs == 0:
                continue  # can't classify without a real follower count

            avg_views_per_video = views / video_count
            # Rough, transparent estimate: engagement proxy from view-to-sub ratio,
            # since per-video likes/comments would cost extra API quota per channel.
            estimated_engagement = min(avg_views_per_video / subs, 0.15) if subs else 0
            avg_likes = int(subs * estimated_engagement * 0.8)
            avg_comments = int(avg_likes * 0.05)

            results.append(RawInfluencer(
                name=snippet.get("title", "Unknown"),
                handle=f"@{snippet.get('title', 'unknown').replace(' ', '')}",
                platform="YouTube",
                profile_url=f"https://youtube.com/channel/{ch['id']}",
                follower_count=subs,
                avg_likes=avg_likes,
                avg_comments=avg_comments,
                niche=niche or "Unclassified",
                content_themes=[niche or "general content"],
                geography=snippet.get("country", "Not Found"),
                audience_age="Not Found",   # not exposed by public API
                audience_gender="Not Found",  # not exposed by public API
                bio=snippet.get("description", "")[:200],
                email_hint=None,  # YouTube API doesn't expose creator emails -- never guessed
                source="youtube_data_api_v3",
            ))
            if len(results) >= min_count:
                break

        return results


def run_discovery(niche: str = config.DEFAULT_NICHE, min_count: int = config.DEFAULT_DISCOVERY_COUNT,
                   kaggle_csv_path: Optional[str] = None, kaggle_niche_keywords: Optional[List[str]] = None,
                   kaggle_max: Optional[int] = None) -> List[dict]:
    """
    Discovery order of preference:
        1. Kaggle real dataset (if kaggle_csv_path given) -- genuine real
           influencer records, tagged source="kaggle_real_dataset". Capped
           at `kaggle_max` (default: ~1/3 of min_count) because public "Top
           N" datasets are dominated by mega-influencers who will correctly
           FAIL the micro-influencer follower-range filter -- including
           all of them would starve the pipeline of any profile that can
           reach enrichment/personalization/sending, leaving nothing to
           demonstrate those stages on. The capped set is still enough to
           prove the filtering logic works correctly against real data.
        2. Live YouTube Data API (if YOUTUBE_API_KEY set) -- genuine real
           channel data, tagged source="youtube_data_api_v3".
        3. Simulated provider tops up the remainder to reach min_count,
           clearly tagged source="simulated_directory", so there's always
           a meaningful pool of micro-range profiles to carry the pipeline
           through filtering -> enrichment -> personalization -> sending.
    """
    records: List[dict] = []
    kaggle_cap = kaggle_max if kaggle_max is not None else max(10, min_count // 3)

    if kaggle_csv_path:
        from src.kaggle_loader import load_kaggle_influencers
        try:
            kaggle_records = load_kaggle_influencers(
                kaggle_csv_path, kaggle_niche_keywords or [niche], niche
            )
            if len(kaggle_records) > kaggle_cap:
                log.info(
                    f"Kaggle CSV matched {len(kaggle_records)} real profiles; capping to {kaggle_cap} "
                    f"so the discovered pool still has room for micro-range profiles that can carry "
                    f"the pipeline through to enrichment/personalization/sending."
                )
                kaggle_records = kaggle_records[:kaggle_cap]
            records.extend(kaggle_records)
            log.info(f"Discovery via Kaggle real dataset: {len(kaggle_records)} real profiles loaded")
        except Exception as e:
            log.error(f"Failed to load Kaggle CSV ({e}); continuing without it")

    if config.YOUTUBE_API_KEY and len(records) < min_count:
        try:
            provider = YouTubeDataAPIProvider()
            yt_records = [asdict(r) for r in provider.discover(niche, min_count - len(records))]
            records.extend(yt_records)
            log.info(f"Discovery via YouTubeDataAPIProvider: {len(yt_records)} real profiles")
        except Exception as e:
            log.warning(f"YouTube provider unavailable ({e})")

    if len(records) < min_count:
        shortfall = min_count - len(records)
        sim_records = [asdict(r) for r in SimulatedDirectoryProvider().discover(niche, shortfall)]
        records.extend(sim_records)
        log.info(f"Topped up with {len(sim_records)} simulated profiles to reach target of {min_count}")

    real_count = sum(1 for r in records if r.get("source") != "simulated_directory")
    log.info(f"Discovery complete: {len(records)} total profiles ({real_count} real, {len(records) - real_count} simulated)")
    return records
