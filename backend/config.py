"""Central configuration for Topic Coverage.

Every threshold, cap, and model choice lives here (CLAUDE.md hard rule:
"All thresholds in config.py — never hardcoded in logic"). Values default to
something that runs fully locally with no API keys, and each is overridable
via an environment variable (and therefore via `.env`, loaded below).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

try:  # .env is optional; defaults stand on their own.
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - dotenv is a declared dep, but stay safe
    pass


# --- small env helpers -------------------------------------------------------

def _env_str(key: str, default: str) -> str:
    val = os.getenv(key)
    return val if val is not None and val != "" else default


def _env_int(key: str, default: int) -> int:
    raw = os.getenv(key)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(key: str, default: float) -> float:
    raw = os.getenv(key)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_bool(key: str, default: bool) -> bool:
    raw = os.getenv(key)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_list(key: str, default: tuple) -> tuple:
    raw = os.getenv(key)
    if raw is None or raw == "":
        return default
    return tuple(s.strip().lower() for s in raw.split(",") if s.strip())


# Path-segment stems for pages that aren't topical content — careers/hiring and
# legal/terms. A URL is dropped if any stem starts a path segment (so "/careers",
# "/en/jobs/123", "/terms-of-service", "/privacy-policy" all match). Override or
# extend via TC_EXCLUDE_URL_PATTERNS (comma-separated).
DEFAULT_EXCLUDE_PATTERNS = (
    # careers / hiring
    "careers", "career", "jobs", "job", "hiring", "hire", "vacancy", "vacancies",
    "opening", "openings", "join-us", "work-with-us", "recruiting", "recruitment",
    "employment", "internship", "internships", "life-at", "apply",
    # legal / terms
    "terms", "tos", "terms-of-service", "terms-and-conditions", "privacy",
    "privacy-policy", "legal", "cookie", "cookies", "gdpr", "dpa", "eula",
    "disclaimer", "imprint",
)


# Project root = the repo dir (parent of backend/).
ROOT_DIR = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Config:
    # --- storage ---
    db_path: Path = field(
        default_factory=lambda: (
            Path(_env_str("TC_DB_PATH", str(ROOT_DIR / "data" / "topic_coverage.db")))
        )
    )

    # --- crawl politeness / caps (SPEC §6.1–6.2) ---
    max_pages_per_domain: int = field(
        default_factory=lambda: _env_int("TC_MAX_PAGES_PER_DOMAIN", 300)
    )
    # Speed vs politeness. Go fast by default; the crawl backs off automatically
    # (host-wide cooldown) the moment a host returns 429/503, so we stay quick on
    # tolerant sites (most) and self-throttle only on strict ones (Shopify etc.).
    # Lower these via env for a gentler crawl.
    per_host_concurrency: int = field(
        default_factory=lambda: _env_int("TC_PER_HOST_CONCURRENCY", 8)
    )
    per_request_delay_seconds: float = field(
        default_factory=lambda: _env_float("TC_PER_REQUEST_DELAY", 0.05)
    )
    request_timeout: float = field(
        default_factory=lambda: _env_float("TC_REQUEST_TIMEOUT", 20.0)
    )
    # Rate-limit handling: retry 429/503 with backoff instead of dropping the
    # page. Honours Retry-After (capped). Without this a throttling host (e.g.
    # Shopify/Cloudflare returning 429) silently yields zero pages.
    fetch_max_retries: int = field(
        default_factory=lambda: _env_int("TC_FETCH_MAX_RETRIES", 5)
    )
    rate_limit_max_wait: float = field(
        default_factory=lambda: _env_float("TC_RATE_LIMIT_MAX_WAIT", 15.0)
    )
    user_agent: str = field(
        default_factory=lambda: _env_str(
            "TC_USER_AGENT",
            "TopicCoverageBot/0.1 (+https://example.com/bot)",
        )
    )
    respect_robots: bool = field(
        default_factory=lambda: _env_bool("TC_RESPECT_ROBOTS", True)
    )
    # Pages to never crawl/compare (careers, legal, etc.) — see notes above.
    exclude_url_patterns: tuple = field(
        default_factory=lambda: _env_list(
            "TC_EXCLUDE_URL_PATTERNS", DEFAULT_EXCLUDE_PATTERNS
        )
    )
    # Per-domain crawl time budget. This is a STALL-GUARD, not a coverage cap:
    # it scales with the number of URLs discovered (seconds_per_url * n_urls) so
    # a large site can be fully crawled, and is only bounded by an absolute
    # ceiling to stop a genuinely stuck/hostile host from running forever.
    # Coverage is capped by max_pages_per_domain (page count), not by time.
    # Set seconds_per_url = 0 for no time limit at all.
    crawl_seconds_per_url: float = field(
        default_factory=lambda: _env_float("TC_CRAWL_SECONDS_PER_URL", 2.0)
    )
    crawl_time_budget_max_seconds: float = field(
        default_factory=lambda: _env_float("TC_CRAWL_TIME_BUDGET_MAX", 1800.0)
    )
    # Ceiling on the sitemap-less focused-crawl fallback (link-following is slow
    # since each page must be fetched to find more). Sites WITH a sitemap aren't
    # affected. The effective cap is min(this, requested max_pages), so asking
    # for fewer pages still stops early. Raised from 80 so sitemap-less sites
    # aren't silently truncated to a fraction of their pages.
    focused_crawl_max_urls: int = field(
        default_factory=lambda: _env_int("TC_FOCUSED_CRAWL_MAX_URLS", 500)
    )
    # Wall-clock limit on the focused-crawl fallback itself (it has no internal
    # timeout and can hang on slow sites). On timeout we proceed with whatever
    # URLs we have (at least the homepage). 0 = no limit. Generous so link
    # discovery has time to reach most of a sitemap-less site.
    focused_crawl_timeout_seconds: float = field(
        default_factory=lambda: _env_float("TC_FOCUSED_CRAWL_TIMEOUT", 120.0)
    )
    # Wall-clock limit on reading/expanding sitemaps (huge sitemap trees, e.g.
    # notion.com, can take very long). On timeout we fall back to a focused
    # crawl, then the homepage. 0 = no limit.
    sitemap_timeout_seconds: float = field(
        default_factory=lambda: _env_float("TC_SITEMAP_TIMEOUT", 30.0)
    )
    # Link augmentation: after crawling the sitemap seed, harvest on-domain links
    # from fetched pages and crawl new ones, this many hops deep. Catches pages a
    # sitemap omits (or when there's no sitemap). 0 disables (sitemap-only).
    # Bounded by max_pages_per_domain and the crawl time budget either way.
    link_augment_rounds: int = field(
        default_factory=lambda: _env_int("TC_LINK_AUGMENT_ROUNDS", 1)
    )

    # --- chunking / embeddings (SPEC §6.4) ---
    chunk_min_tokens: int = field(
        default_factory=lambda: _env_int("TC_CHUNK_MIN_TOKENS", 200)
    )
    chunk_max_tokens: int = field(
        default_factory=lambda: _env_int("TC_CHUNK_MAX_TOKENS", 500)
    )
    chunk_overlap_tokens: int = field(
        default_factory=lambda: _env_int("TC_CHUNK_OVERLAP_TOKENS", 40)
    )
    embedding_backend: str = field(
        default_factory=lambda: _env_str("TC_EMBEDDING_BACKEND", "local")
    )
    local_embedding_model: str = field(
        default_factory=lambda: _env_str(
            "TC_LOCAL_EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5"
        )
    )

    # --- language-similarity scoring (homepage compare) ---
    # Most competitor domains accepted per comparison.
    max_competitors: int = field(
        default_factory=lambda: _env_int("TC_MAX_COMPETITORS", 5)
    )
    # Lexical score blends shared-vocabulary (unigram) and shared-phrasing
    # (bigram) overlap. Weights sum to 1.0; lean bigram to reward copied phrasing.
    lexical_unigram_weight: float = field(
        default_factory=lambda: _env_float("TC_LEXICAL_UNIGRAM_WEIGHT", 0.5)
    )
    lexical_bigram_weight: float = field(
        default_factory=lambda: _env_float("TC_LEXICAL_BIGRAM_WEIGHT", 0.5)
    )

    # --- topic discovery (SPEC §6.4) ---
    min_cluster_size: int = field(
        default_factory=lambda: _env_int("TC_MIN_CLUSTER_SIZE", 8)
    )
    umap_n_neighbors: int = field(
        default_factory=lambda: _env_int("TC_UMAP_N_NEIGHBORS", 15)
    )
    num_categories_min: int = field(
        default_factory=lambda: _env_int("TC_NUM_CATEGORIES_MIN", 8)
    )
    num_categories_max: int = field(
        default_factory=lambda: _env_int("TC_NUM_CATEGORIES_MAX", 14)
    )

    # --- coverage scoring (SPEC §6.5–6.6) ---
    sim_threshold: float = field(
        default_factory=lambda: _env_float("TC_SIM_THRESHOLD", 0.35)
    )
    parity_delta: float = field(
        default_factory=lambda: _env_float("TC_PARITY_DELTA", 0.10)
    )

    # --- optional hosted upgrades ---
    openai_api_key: str = field(
        default_factory=lambda: _env_str("OPENAI_API_KEY", "")
    )
    anthropic_api_key: str = field(
        default_factory=lambda: _env_str("ANTHROPIC_API_KEY", "")
    )
    # LLM topic/category labels (optional). Off by default so the repo runs with
    # no keys; when on, topics.py names clusters with a model instead of
    # term-based labels. Provider is switchable:
    #   anthropic -> Claude (needs ANTHROPIC_API_KEY)
    #   ollama    -> local open model (free, no key; needs Ollama running)
    llm_labels: bool = field(
        default_factory=lambda: _env_bool("TC_LLM_LABELS", False)
    )
    llm_provider: str = field(
        default_factory=lambda: _env_str("TC_LLM_PROVIDER", "anthropic")
    )
    llm_model: str = field(
        default_factory=lambda: _env_str("TC_LLM_MODEL", "qwen2.5:3b")
    )
    ollama_host: str = field(
        default_factory=lambda: _env_str("TC_OLLAMA_HOST", "http://localhost:11434")
    )

    # --- explanation LLM (homepage-compare "why") ---
    # One OpenAI-compatible client for every provider. Default = local Ollama
    # (free, no key). For deploy, just repoint these three env vars, e.g. Groq:
    #   TC_LLM_BASE_URL=https://api.groq.com/openai/v1
    #   TC_LLM_MODEL=llama-3.1-8b-instant     TC_LLM_API_KEY=gsk_...
    # Explanation is optional: a deterministic fallback runs whenever the
    # endpoint is unset/unreachable, so the product never breaks on the LLM.
    explanation_enabled: bool = field(
        default_factory=lambda: _env_bool("TC_EXPLANATION", True)
    )
    llm_base_url: str = field(
        default_factory=lambda: _env_str("TC_LLM_BASE_URL", "http://localhost:11434/v1")
    )
    llm_api_key: str = field(
        default_factory=lambda: _env_str("TC_LLM_API_KEY", "")
    )
    llm_timeout: float = field(
        default_factory=lambda: _env_float("TC_LLM_TIMEOUT", 60.0)
    )

    # --- language ---
    default_market_language: str = field(
        default_factory=lambda: _env_str("TC_MARKET_LANGUAGE", "en")
    )

    def ensure_dirs(self) -> None:
        """Create any directories the config implies (e.g. the DB folder)."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def crawl_deadline_for(self, n_urls: int) -> Optional[float]:
        """Wall-clock stall-guard for crawling `n_urls` pages of one domain.
        Scales with the work (so a big site isn't truncated) but is capped by an
        absolute ceiling. Returns None for 'no limit'."""
        if self.crawl_seconds_per_url <= 0:
            return None  # unlimited
        deadline = self.crawl_seconds_per_url * max(1, n_urls)
        if self.crawl_time_budget_max_seconds > 0:
            deadline = min(deadline, self.crawl_time_budget_max_seconds)
        return deadline


# The 5 coverage states and their colours (SPEC §2). Kept here so both the API
# and any server-side rendering share one source of truth with the frontend.
STATE_COLORS = {
    "only_you": "#15803d",
    "you_lead": "#22c55e",
    "even": "#94a3b8",
    "comp_lead": "#fb923c",
    "only_comp": "#ef4444",
}
COVERAGE_STATES: List[str] = list(STATE_COLORS.keys())


# A single shared instance. Import `config` everywhere.
config = Config()
