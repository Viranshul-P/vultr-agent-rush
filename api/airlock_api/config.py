"""Settings from environment variables (see deploy/.env.control.example)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


@dataclass
class Settings:
    domain: str = field(default_factory=lambda: _env("DOMAIN", "localhost"))
    public_base_url: str = field(default_factory=lambda: _env("PUBLIC_BASE_URL", ""))

    inference_base_url: str = field(default_factory=lambda: _env("VULTR_INFERENCE_BASE_URL", "https://api.vultrinference.com/v1"))
    inference_api_key: str = field(default_factory=lambda: _env("VULTR_INFERENCE_API_KEY"))
    llm_mode: str = field(default_factory=lambda: _env("LLM_MODE", ""))  # "vultr" | "mock" (auto if empty)
    model_coder: str = field(default_factory=lambda: _env("MODEL_CODER", "glm-5.3"))
    model_planner: str = field(default_factory=lambda: _env("MODEL_PLANNER", "glm-5.3-flash"))
    model_vision: str = field(default_factory=lambda: _env("MODEL_VISION", "qwen3.8-flash-next"))
    model_safety: str = field(default_factory=lambda: _env("MODEL_SAFETY", "nemotron-3.5-content-safety"))
    model_fallback: str = field(default_factory=lambda: _env("MODEL_FALLBACK", "deepseek-v4.1-flash-1017"))
    llm_temperature: float = field(default_factory=lambda: float(_env("LLM_TEMPERATURE", "0.1")))
    llm_timeout_s: float = field(default_factory=lambda: float(_env("LLM_TIMEOUT_S", "90")))  # code-writing + vision
    # safety / classifier / planner: short calls, so a long wait means a stuck call -> fall back sooner
    # Invoices processed at once across ALL visitors (bounds load on the sandbox VM and the inference API).
    pipeline_workers: int = field(default_factory=lambda: int(_env("PIPELINE_WORKERS", "3")))
    llm_fast_timeout_s: float = field(default_factory=lambda: float(_env("LLM_FAST_TIMEOUT_S", "45")))
    llm_max_retries: int = field(default_factory=lambda: int(_env("LLM_MAX_RETRIES", "1")))
    llm_max_tokens: int = field(default_factory=lambda: int(_env("LLM_MAX_TOKENS", "6000")))
    llm_reasoning_effort: str = field(default_factory=lambda: _env("LLM_REASONING_EFFORT", "low"))  # "" disables
    llm_coder_reasoning_effort: str = field(default_factory=lambda: _env("LLM_CODER_REASONING_EFFORT", "medium"))
    llm_coder_max_tokens: int = field(default_factory=lambda: int(_env("LLM_CODER_MAX_TOKENS", "14000")))

    database_url: str = field(default_factory=lambda: _env("DATABASE_URL", f"sqlite:///{(ROOT / 'var' / 'airlock.db').as_posix()}"))
    storage_dir: str = field(default_factory=lambda: _env("STORAGE_DIR", str(ROOT / "var" / "storage")))
    s3_endpoint: str = field(default_factory=lambda: _env("S3_ENDPOINT"))
    s3_access_key: str = field(default_factory=lambda: _env("S3_ACCESS_KEY"))
    s3_secret_key: str = field(default_factory=lambda: _env("S3_SECRET_KEY"))
    s3_bucket: str = field(default_factory=lambda: _env("S3_BUCKET", "airlock"))

    runner_url: str = field(default_factory=lambda: _env("RUNNER_URL", "http://127.0.0.1:8700"))
    runner_token: str = field(default_factory=lambda: _env("RUNNER_TOKEN"))

    signing_key_b64: str = field(default_factory=lambda: _env("SIGNING_KEY_ED25519"))
    daily_token_budget: int = field(default_factory=lambda: int(_env("DAILY_TOKEN_BUDGET", "3000000")))
    max_upload_mb: int = field(default_factory=lambda: int(_env("MAX_UPLOAD_MB", "5")))
    uploads_per_hour_per_ip: int = field(default_factory=lambda: int(_env("UPLOADS_PER_HOUR_PER_IP", "10")))
    seed_dir: str = field(default_factory=lambda: _env("AIRLOCK_SEED_DIR", str(ROOT / "seed")))
    max_code_attempts: int = 3
    max_links: int = 3

    @property
    def mode(self) -> str:
        if self.llm_mode in ("vultr", "mock"):
            return self.llm_mode
        return "vultr" if self.inference_api_key else "mock"


settings = Settings()
