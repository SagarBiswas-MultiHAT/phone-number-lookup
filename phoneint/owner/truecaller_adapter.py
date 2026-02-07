"""Stub Truecaller owner adapter."""

from __future__ import annotations

import logging
from typing import Any

from httpx import AsyncClient
from phoneint.net.http import HttpClientConfig
from .interface import LegalBasis, OwnerAdapter, OwnerAdapterResult

logger = logging.getLogger(__name__)


class TruecallerAdapter(OwnerAdapter):
    name = "truecaller"
    pii_capable = True

    def __init__(
        self,
        *,
        client: AsyncClient,
        http_config: HttpClientConfig,
        enabled: bool,
        api_key: str | None,
        rate_limiter: Any | None,
    ) -> None:
        self._client = client
        self._enabled = enabled
        self._api_key = api_key
        self._http_config = http_config
        self._rate_limiter = rate_limiter

    async def lookup_owner(
        self,
        e164: str,
        *,
        legal_basis: LegalBasis | None,
        limit: int = 5,
        caller: str | None = None,
    ) -> OwnerAdapterResult:
        if not self._enabled or not self._api_key:
            raise PermissionError("Truecaller adapter is not enabled or missing API key")
        if legal_basis is None or legal_basis.get("consent_obtained") is not True:
            raise PermissionError("Explicit consent is required")

        logger.debug("Truecaller lookup stub: %s", e164)
        # Real Truecaller integration is not implemented; return empty result for now.
        return OwnerAdapterResult(associations=[], pii=None)
