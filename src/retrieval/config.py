"""Settings. Everything is driven by environment variables (optionally a .env file),
so adding an API key later is a one-line change and needs no code edits.

See .env.example. Retrieval defaults to hashing and lexical reranking, which
run locally. Set EMBEDDING_PROVIDER=auto to opt in to key-based selection.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


def load_dotenv(path: Optional[Path] = None) -> None:
    """Tiny .env loader (no dependency). Real environment variables win over the file."""
    path = path or Path(os.environ.get("POD_B_ENV_FILE", ".env"))
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _get(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _api_key(name: str) -> str:
    value = _get(name)
    if value.lower() == f"your_{name.lower()}_here":
        return ""
    return value


@dataclass(frozen=True)
class Settings:
    embedding_provider: str  # auto | openai | gemini | local | hash
    embedding_model: str  # "" => provider default
    rerank_provider: str  # auto | cross-encoder | lexical | none
    rerank_model: str
    openai_api_key: str
    gemini_api_key: str
    cache_dir: Path
    candidate_pool: int  # how many fused candidates go to the reranker
    llm_provider: str = "auto"  # auto | gemini | none
    llm_model: str = ""  # "" => provider default
    verify_with_llm: bool = False  # extra LLM call that fact-checks each claim against its cited units
    admin_token: str = ""  # if set, ingest/rebuild endpoints require header X-Admin-Token
    rate_limit_per_min: int = 60  # per client IP on /ask (it spends LLM calls); 0 disables
    cors_origins: str = "http://localhost:3000,http://localhost:5173,http://127.0.0.1:5173"  # comma list or "*"
    sources_dir: str = ""  # if set, GET /sources/{source_id} serves the original files from here
    replicate_api_key: str = ""
    groq_api_key: str = ""

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        return cls(
            embedding_provider=(_get("EMBEDDING_PROVIDER") or "hash").lower(),
            embedding_model=_get("EMBEDDING_MODEL"),
            rerank_provider=(_get("RERANK_PROVIDER") or "lexical").lower(),
            rerank_model=_get("RERANK_MODEL"),
            openai_api_key=_api_key("OPENAI_API_KEY"),
            gemini_api_key=_api_key("GEMINI_API_KEY") or _api_key("GOOGLE_API_KEY"),
            cache_dir=Path(_get("POD_B_CACHE_DIR", ".pod_b_cache")),
            candidate_pool=int(_get("CANDIDATE_POOL", "20")),
            llm_provider=_get("LLM_PROVIDER", "auto").lower(),
            llm_model=_get("LLM_MODEL"),
            verify_with_llm=_get("VERIFY_WITH_LLM", "0").lower() in ("1", "true", "yes"),
            admin_token=_get("POD_B_ADMIN_TOKEN"),
            rate_limit_per_min=int(_get("POD_B_RATE_LIMIT", "60")),
            cors_origins=_get("POD_B_CORS_ORIGINS", "http://localhost:3000,http://localhost:5173,http://127.0.0.1:5173"),
            sources_dir=_get("POD_B_SOURCES_DIR"),
            replicate_api_key=_api_key("REPLICATE_API_KEY") or _api_key("REPLICATE_API_TOKEN"),
            groq_api_key=_api_key("GROQ_API_KEY"),
        )
