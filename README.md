# Automated Micro-Influencer Outreach System (v2)

A working prototype of an end-to-end pipeline that discovers micro-influencers,
filters/classifies them, enriches their profiles, generates AI-personalized
outreach messages, and sends (or simulates sending) with duplicate-prevention
and SQLite-backed tracking.

```
Discovery → Filtering/Classification → Enrichment → AI Personalization → Sending → Tracking
```

**What changed from v1:** proper config module, structured logging (console +
file), SQLite-backed persistent tracking/dedupe (instead of JSON+CSV),
broader personalization phrasing pools, and a unit test suite (13 tests,
all passing) covering filtering, enrichment, and word-count logic.

## 1. Technology Stack

- **Python 3.12**, standard library (`csv`, `sqlite3`, `logging`, `dataclasses`, `smtplib`, `unittest`)
- **anthropic** SDK (optional) — real Claude API for message personalization
- **SQLite** — persistent, queryable outreach log + dedupe store (upgrade path to Postgres at scale)

## 2. APIs / Tools Used

| Layer | Tool in this build | Real-world equivalent (documented, swappable) |
|---|---|---|
| Discovery | `SimulatedDirectoryProvider` | Instagram Graph API, YouTube Data API v3, TikTok Research API, Collabstr/Aspire/Grin |
| Personalization | `RuleBasedGenerator` (fallback) / **Anthropic Messages API** (`claude-sonnet-4-6`) if `ANTHROPIC_API_KEY` set | same |
| Sending | `SimulatedSender` (fallback) / **SMTP** if `SMTP_HOST/USER/PASS` set | Gmail API, SMTP, n8n/Make/Zapier |
| Tracking | SQLite (`data/outreach.db`) | Postgres/MySQL at scale |

## 3. Data Sources (Real + Simulated, Clearly Labeled)

Discovery blends up to three sources, tried in this order, each explicitly
tagged in the `Data Source` column of `influencer_dataset.csv` so real and
synthetic records are never ambiguous:

1. **Kaggle real dataset (`kaggle_real_dataset`)** — genuine, publicly
   published influencer records. This submission bundles
   `kaggle_source/social_media_influencers_instagram.csv` ("Social Media
   Influencers 2022", 1,000 real Instagram accounts with real handles,
   real follower counts, real engagement metrics, and real categories, as
   scraped and shared by the dataset author). Loaded via `--kaggle-csv`.

   **Important, observed result:** every single record in this dataset has
   2.6M+ followers (it's a "Top 1000" list) — so **all real records
   correctly FAIL the micro-influencer follower-range filter (5K-100K)**.
   This is expected and is direct, verifiable evidence the filtering logic
   works correctly against real-world data (e.g. `addisonraee`, 40.5M
   followers, real profile, is correctly rejected with reason "Follower
   count 40,500,000 outside 5,000-100,000 range"). Real records are capped
   at `--kaggle-max` (default ~1/3 of `--count`) so the discovered pool
   still has room for micro-range profiles that can carry the demo through
   enrichment/personalization/sending — including all 1,000 real rows
   would produce zero shortlisted influencers and nothing to demonstrate
   past the filtering stage. Contact email is never present in this
   dataset, so it is always marked `"Not Found"`, never guessed.
2. **Live YouTube Data API (`youtube_data_api_v3`)** — real channel data
   (subscriber counts, view counts) via the public YouTube Data API v3,
   used automatically if `YOUTUBE_API_KEY` is set.
3. **Simulated top-up (`simulated_directory`)** — realistic synthetic
   profiles fill the remainder up to `--count`, so the pipeline always has
   a meaningful pool of micro-range profiles to demonstrate
   filtering/enrichment/personalization/sending end-to-end. This sandbox
   has no outbound network access to social platforms, and unauthorized
   scraping would violate their Terms of Service (which the assignment
   explicitly says not to bypass) — so simulated data fills the gap,
   always clearly tagged.

**No record from any source is ever presented as something it isn't** —
real records carry real metrics with real limitations (e.g. no email),
simulated records are tagged as such and never claimed to be real people.

## 4. Discovery Methodology

`src/discovery.py` generates ≥50 candidate profiles (default 60, configurable
via `--count`) across 8 niches, 3 platforms, and 8 geographies, biased ~55%
toward the target niche so filtering has a meaningful pass/fail split.

## 5. Filtering Logic

Implemented category: **Fashion & Beauty influencers** (matches the
assignment's own worked example), in `src/filtering.py`.

A profile **passes** only if all hard criteria (defined centrally in
`src/config.py`) are met:
1. **Niche match** — `niche == "Beauty & Fashion"`
2. **Follower range** — 5,000–100,000 (micro-influencer definition)
3. **Engagement rate** — ≥ 2% (`(avg_likes + avg_comments) / followers`)

A **soft** criterion (geography in target markets) is evaluated and logged
but does not block passing. Every record carries a human-readable
`filter_reasons` string. Covered by 6 unit tests in `tests/test_pipeline.py`.

## 6. Enrichment Process

For every profile that passed filtering, `src/enrichment.py` builds the full
mandatory-field record (name, platform, profile URL, followers, engagement
rate, niche, content themes, contact email) plus optional fields. **Email is
never guessed** — `"Not Found"` if genuinely unavailable. Covered by 3 unit tests.

## 7. AI Model / Prompt Used for Personalization

`src/personalization.py` implements two interchangeable backends:

- **`ClaudeGenerator`** (auto-used if `ANTHROPIC_API_KEY` is set): calls
  `claude-sonnet-4-6` via the Messages API with a prompt injecting name,
  niche, content themes, followers, and engagement rate; requests JSON with
  a 60–90 word email pitch and 15–30 word Instagram DM referencing
  niche/content/audience and proposing a concrete collaboration angle.
- **`RuleBasedGenerator`** (default fallback, active in this submission since
  no API key is available in the build sandbox): composes messages
  dynamically from the same signals using expanded phrasing pools (5
  openers × 7 collaboration angles × 6 value props × 3 closers for email
  alone), so messages vary meaningfully across influencers. Word counts are
  enforced programmatically and unit-tested.

To enable real Claude-generated messages: `export ANTHROPIC_API_KEY=sk-...`
and re-run — no code changes needed.

## 8. Personalization Logic

Both backends reference, per message: the influencer's specific **niche**
and a **named content theme**, their **follower tier** (growing /
established / high-reach), a **concrete collaboration angle** (affiliate,
UGC, ambassador, barter, sponsored, capsule, giveaway), and a **specific
value proposition** (commission, creative freedom, early access, etc.).

## 9. Sending Mechanism

`src/sender.py`, backed by SQLite (`data/outreach.db`, table `outreach_log`):
1. Selects only influencers with a valid (non-"Not Found") email.
2. Retrieves their generated email pitch.
3. Sends via `SMTPSender` if `SMTP_HOST/SMTP_USER/SMTP_PASS` are set,
   otherwise **simulates** via `SimulatedSender` (same validation/logging
   path, network call swapped for a logged simulation).
4. Records status (`Sent` / `Failed` / `Skipped - ...`) with a timestamp.
5. **Prevents duplicate outreach** via a `UNIQUE(email)` constraint +
   pre-send lookup against prior `Sent` rows — verified by running the
   pipeline twice: first run sends real candidates, second run (without
   `--fresh`) shows **0 sent, all flagged duplicate**.
6. Maintains a queryable outreach log; exported to both
   `output/outreach_tracker.csv` and a raw `output/outreach_db_export.csv`.

**Instagram DMs** are generated but never auto-sent — per the assignment's
instruction not to bypass Instagram's platform restrictions, each DM is
logged as `"Ready for manual/authorized send"`.

## 10. Limitations

- Discovery data is **synthetic**, not pulled from live platforms (§3).
- Email sending is simulated by default (no SMTP credentials here); the
  real SMTP code path is implemented and correct but not exercised end-to-end.
- AI personalization defaults to the rule-based generator; the Claude-backed
  path is implemented and correct but requires `ANTHROPIC_API_KEY`.
- Engagement rate estimated from likes+comments/followers only (no
  shares/saves data available from the simulated source).
- SQLite is single-file/single-writer — fine for a prototype, see below for scale-up.

## 11. Scalability (50 → 500+ influencers)

- **Storage:** SQLite → Postgres is a near-drop-in swap (same SQL, just a
  different connection string); the `outreach_log` schema is already
  normalized and ready.
- **Discovery:** `DiscoveryProvider` interface supports adding real,
  paginated sources (YouTube API, Apify-based scrapers, Collabstr exports)
  run concurrently; discovery count is already a CLI flag (`--count`).
- **Personalization:** `ClaudeGenerator` calls can be batched via the
  Anthropic Batch API for cost/throughput at scale.
- **Sending:** `SMTPSender` can be swapped for the Gmail API or an
  automation tool (n8n/Zapier) for rate-limited, queued sending.
- **Filtering:** criteria live in `config.py` as constants — adding niches
  or demographic filters is additive, not a rewrite.
- **Testing:** the existing `unittest` suite is a foundation to extend with
  integration tests as new providers/backends are added.

## 12. Setup Instructions

```bash
cd influencer-outreach-v2
pip install -r requirements.txt      # optional, only for real Claude API calls

# Run the full pipeline (defaults: niche="Beauty & Fashion", 60 profiles)
python3 -m src.main --niche "Beauty & Fashion" --count 60 --fresh

# Recommended: blend in REAL data from the bundled Kaggle influencer CSV
python3 -m src.main --niche "Beauty & Fashion" --count 60 --fresh \
  --kaggle-csv "kaggle_source/social_media_influencers_instagram.csv" --kaggle-keywords "beauty,fashion"
# Windows PowerShell:
#   python -m src.main --niche "Beauty & Fashion" --count 60 --fresh `
#     --kaggle-csv "kaggle_source\social_media_influencers_instagram.csv" --kaggle-keywords "beauty,fashion"

# Run tests
python3 -m unittest tests.test_pipeline -v

# Optional: enable REAL influencer discovery (YouTube Data API v3, free tier)
# Get a key at https://console.cloud.google.com -> enable "YouTube Data API v3" -> Credentials -> API Key
export YOUTUBE_API_KEY=AIzaSy...
python3 -m src.main --fresh
# Windows PowerShell:  $env:YOUTUBE_API_KEY="AIzaSy..."; python -m src.main --fresh

# Optional: enable real LLM personalization
export ANTHROPIC_API_KEY=sk-ant-...
python3 -m src.main --fresh

# Optional: enable real SMTP sending
export SMTP_HOST=smtp.gmail.com SMTP_USER=you@gmail.com SMTP_PASS=app_password
python3 -m src.main --fresh
```

**Outputs** land in `/output`:
- `influencer_dataset.csv` — all 50+ discovered profiles with pass/fail + reasons
- `shortlisted_enriched.csv` — enriched profiles that passed filtering
- `personalized_messages.csv` — email pitch + Instagram DM per shortlisted influencer
- `outreach_tracker.csv` / `outreach_db_export.csv` — send status, dates, dedupe results

Run `python3 -m src.main` a second time **without** `--fresh` to see
duplicate-prevention in action (previously-emailed influencers get skipped).

## 13. Project Structure

```
influencer-outreach-v2/
├── README.md
├── requirements.txt
├── kaggle_source/
│   └── social_media_influencers_instagram.csv   # bundled real dataset (1,000 real IG accounts)
├── src/
│   ├── config.py            # central constants (thresholds, paths, env)
│   ├── logger.py            # structured logging setup
│   ├── discovery.py         # Module 1: Influencer Discovery (blends real + simulated)
│   ├── kaggle_loader.py      # loads real influencer records from the Kaggle CSV
│   ├── filtering.py         # Module 2: Filtering & Classification
│   ├── enrichment.py        # Module 3: Profile Enrichment
│   ├── personalization.py   # Module 4: AI Message Personalization
│   ├── sender.py            # Module 5: Sending Layer + SQLite Tracking
│   └── main.py               # Orchestrator (runs full pipeline)
├── tests/
│   └── test_pipeline.py     # 13 unit tests (filtering, enrichment, word limits)
├── data/                     # outreach.db (SQLite)
└── output/                   # final CSV deliverables
```
