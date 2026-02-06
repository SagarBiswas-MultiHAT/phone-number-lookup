# file: phoneint/config.py
"""
Configuration loader.

Design goals:
- No secrets committed to the repo.
- Support `.env` for local development.
- Support YAML for weight tuning and non-secret defaults.
- Validate configuration with pydantic.

Precedence (highest to lowest):
1. OS environment variables
2. `.env` values
3. YAML config file values
4. Code defaults
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import dotenv_values
from pydantic import BaseModel, Field
from pydantic import ConfigDict as PydanticConfigDict

from phoneint.net.http import HttpClientConfig
from phoneint.reputation.score import default_score_weights


class PhoneintSettings(BaseModel):
    model_config = PydanticConfigDict(extra="ignore")

    # General
    default_region: str | None = None
    log_level: str = "INFO"
    json_logging: bool = False

    # HTTP
    http_timeout_seconds: float = 10.0
    http_max_retries: int = 2
    http_backoff_base_seconds: float = 0.5
    http_backoff_max_seconds: float = 8.0
    http_rate_limit_per_host_per_second: float = 1.0
    http_user_agent: str = "phoneint/0.1 (+https://example.invalid; lawful OSINT only)"

    # Cache
    cache_enabled: bool = True
    cache_path: Path = Path(".cache/phoneint.sqlite3")
    cache_ttl_seconds: int = 3600

    # Adapters
    gcs_api_key: str | None = Field(default=None)
    gcs_cx: str | None = Field(default=None)
    scam_list_path: Path | None = None

    # Scoring
    score_weights: dict[str, float] = Field(default_factory=default_score_weights)

    def http_config(self) -> HttpClientConfig:
        return HttpClientConfig(
            timeout_seconds=self.http_timeout_seconds,
            max_retries=self.http_max_retries,
            backoff_base_seconds=self.http_backoff_base_seconds,
            backoff_max_seconds=self.http_backoff_max_seconds,
            rate_limit_per_host_per_second=self.http_rate_limit_per_host_per_second,
            user_agent=self.http_user_agent,
        )


_ENV_MAP: dict[str, str] = {
    "GCS_API_KEY": "gcs_api_key",
    "GCS_CX": "gcs_cx",
    "PHONEINT_DEFAULT_REGION": "default_region",
    "PHONEINT_LOG_LEVEL": "log_level",
    "PHONEINT_JSON_LOGGING": "json_logging",
    "PHONEINT_HTTP_TIMEOUT_SECONDS": "http_timeout_seconds",
    "PHONEINT_HTTP_MAX_RETRIES": "http_max_retries",
    "PHONEINT_HTTP_BACKOFF_BASE_SECONDS": "http_backoff_base_seconds",
    "PHONEINT_HTTP_BACKOFF_MAX_SECONDS": "http_backoff_max_seconds",
    "PHONEINT_HTTP_RATE_LIMIT_PER_HOST_PER_SECOND": "http_rate_limit_per_host_per_second",
    "PHONEINT_HTTP_USER_AGENT": "http_user_agent",
    "PHONEINT_CACHE_ENABLED": "cache_enabled",
    "PHONEINT_CACHE_PATH": "cache_path",
    "PHONEINT_CACHE_TTL_SECONDS": "cache_ttl_seconds",
    "PHONEINT_SCAM_LIST_PATH": "scam_list_path",
    # JSON string: {"found_in_scam_db": 70, "voip": 10, ...}
    "PHONEINT_SCORE_WEIGHTS": "score_weights",
}


def _read_yaml(path: Path) -> dict[str, Any]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return raw if isinstance(raw, dict) else {}


def _read_dotenv(path: Path) -> dict[str, str]:
    # dotenv_values does not mutate os.environ; it just parses the file.
    values = dotenv_values(path)
    out: dict[str, str] = {}
    for k, v in values.items():
        if isinstance(k, str) and isinstance(v, str):
            out[k] = v
    return out


def _overlay_env(target: dict[str, Any], env: dict[str, str]) -> None:
    for env_key, field_name in _ENV_MAP.items():
        if env_key not in env:
            continue
        raw = env[env_key]
        if field_name == "score_weights":
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                target[field_name] = parsed
        else:
            target[field_name] = raw


def load_settings(
    *, yaml_path: Path | None = None, env_path: Path | None = None
) -> PhoneintSettings:
    """
    Load settings from YAML and .env, with OS env overrides.

    Args:
        yaml_path: Optional YAML config path.
        env_path: Optional .env path (default: `.env` if present).
    """

    data: dict[str, Any] = {}

    # Load .env file if provided or default to ./ .env
    if env_path is None:
        maybe = Path(".env")
        env_path = maybe if maybe.exists() else None

    dotenv = _read_dotenv(env_path) if env_path is not None and env_path.exists() else {}

    # YAML path resolution:
    # - explicit yaml_path wins
    # - else PHONEINT_CONFIG from OS env wins
    # - else PHONEINT_CONFIG from .env
    if yaml_path is None:
        cfg = os.environ.get("PHONEINT_CONFIG") or dotenv.get("PHONEINT_CONFIG")
        if cfg:
            yaml_path = Path(cfg)

    if yaml_path is not None and yaml_path.exists():
        data.update(_read_yaml(yaml_path))

    if dotenv:
        _overlay_env(data, dotenv)

    # OS env overrides .env/YAML
    os_env: dict[str, str] = {k: v for k, v in os.environ.items() if k in _ENV_MAP}
    _overlay_env(data, os_env)

    return PhoneintSettings.model_validate(data)
