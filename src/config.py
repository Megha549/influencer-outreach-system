"""
config.py
---------
Central configuration for the entire pipeline. Keeping all tunable
constants in one place makes the system easier to extend/scale
(e.g. changing niche, thresholds, or DB path doesn't require touching
business logic files).
"""

import os

# ---- Discovery ----
DEFAULT_NICHE = "Beauty & Fashion"
DEFAULT_DISCOVERY_COUNT = 60
RANDOM_SEED = 42

# ---- Filtering & Classification ----
MIN_FOLLOWERS = 5_000
MAX_FOLLOWERS = 100_000
MIN_ENGAGEMENT_RATE = 0.02  # 2%
TARGET_GEOGRAPHIES = {"US", "UK", "India", "Canada", "Australia"}

# ---- Personalization ----
CLAUDE_MODEL = "claude-sonnet-4-6"
EMAIL_MIN_WORDS, EMAIL_MAX_WORDS = 60, 90
DM_MIN_WORDS, DM_MAX_WORDS = 15, 30

# ---- Paths ----
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
DB_PATH = os.path.join(DATA_DIR, "outreach.db")
LOG_PATH = os.path.join(BASE_DIR, "pipeline.log")

# ---- Env-driven backend selection ----
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
SMTP_HOST = os.environ.get("SMTP_HOST")
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASS = os.environ.get("SMTP_PASS")
SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")
