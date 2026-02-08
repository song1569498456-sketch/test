from __future__ import annotations

import asyncio
import random
from typing import Any

import httpx

from src.quote.base import QuoteResult


class OneInchQuoteProvider:
    def __init__(self, chain_id: int, tokens: dict[str, Any], oneinch_cfg: dict[str, Any]) -> None:
        self.chain_id = chain_id
        self.tokens = tokens
        self.base_url = oneinch_cfg["base_url"].rstrip("/")
        self.timeout_sec = oneinch_cfg["timeout_sec"]
        self.max_retries = oneinch_cfg["max_retries"]
        self.api_key = oneinch_cfg.get("api_key", "")
        self.client = httpx.AsyncClient(timeout=self.timeout_sec)

    async def close(self) -> None:
        await self.client.aclose()

    async def quote(self, token_in: str, token_out: str, amount_in_wei: int) -> QuoteResult:
        t_in = self.tokens[token_in]
        t_out = self.tokens[token_out]
        endpoint = f"{self.base_url}/{self.chain_id}/quote"
        params = {
            "src": t_in["address"],
            "dst": t_out["address"],
            "amount": str(amount_in_wei),
        }
        headers = {"accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        last_error = "unknown"
        status = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = await self.client.get(endpoint, params=params, headers=headers)
                status = resp.status_code
                if status in {429, 500, 502, 503, 504}:
                    last_error = f"retryable_http_{status}"
                    if attempt < self.max_retries:
                        delay = (2**attempt) * 0.25 + random.uniform(0, 0.2)
                        await asyncio.sleep(delay)
                        continue
                resp.raise_for_status()
                payload = resp.json()
                out_raw = payload.get("dstAmount") or payload.get("toTokenAmount")
                if out_raw is None:
                    return QuoteResult(
                        ok=False,
                        amount_in_wei=amount_in_wei,
                        amount_out_wei=0,
                        token_in=token_in,
                        token_out=token_out,
                        meta={"endpoint": endpoint, "http_status": status},
                        error="missing_dst_amount",
                    )
                return QuoteResult(
                    ok=True,
                    amount_in_wei=amount_in_wei,
                    amount_out_wei=int(out_raw),
                    token_in=token_in,
                    token_out=token_out,
                    meta={
                        "endpoint": endpoint,
                        "http_status": status,
                        "protocols": payload.get("protocols"),
                        "estimatedGas": payload.get("estimatedGas"),
                    },
                )
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)
                if attempt < self.max_retries:
                    delay = (2**attempt) * 0.25 + random.uniform(0, 0.2)
                    await asyncio.sleep(delay)
                    continue

        return QuoteResult(
            ok=False,
            amount_in_wei=amount_in_wei,
            amount_out_wei=0,
            token_in=token_in,
            token_out=token_out,
            meta={"endpoint": endpoint, "http_status": status},
            error=last_error,
        )
