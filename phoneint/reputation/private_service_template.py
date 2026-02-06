# file: phoneint/reputation/private_service_template.py
"""
Template for integrating an official, permitted third-party reputation service.

Important:
    - Do NOT scrape private sites or bypass authentication.
    - Only integrate services via their official APIs/SDKs with explicit permission.
    - Ensure you comply with Terms of Service, privacy laws, and rate limits.

This module is a non-functional skeleton on purpose.
"""

from __future__ import annotations

from phoneint.reputation.adapter import ReputationAdapter, SearchResult


class OfficialServiceAdapter(ReputationAdapter):
    """
    Example adapter skeleton.

    Replace `SERVICE_API_KEY`/`SERVICE_ENDPOINT` with your service's official API.
    """

    name = "official_service"

    def __init__(self, *, api_key: str | None = None) -> None:
        self._api_key = api_key

    async def check(self, e164: str, *, limit: int = 5) -> list[SearchResult]:
        raise RuntimeError(
            "This is a template only. Integrate official third-party services via their permitted APIs "
            "and keep credentials in .env (never commit secrets)."
        )
