from __future__ import annotations

from decimal import Decimal
from typing import Any

from src.tokens import from_wei, to_wei


def find_stable_symbol(tokens: dict[str, Any]) -> str | None:
    for s, t in tokens.items():
        if t.get("is_stable"):
            return s
    return None


async def infer_token_usd(
    token_symbol: str,
    tokens: dict[str, Any],
    quote_provider,
    mode: str,
    static_prices: dict[str, float] | None = None,
) -> tuple[float | None, str]:
    token = tokens[token_symbol]
    if token.get("is_stable"):
        return 1.0, "stable_peg"

    static_prices = static_prices or {}
    if mode == "static":
        v = token.get("static_price_usd") or static_prices.get(token_symbol)
        return (float(v), "static") if v is not None else (None, "static_missing")

    stable = find_stable_symbol(tokens)
    if not stable:
        return None, "infer_no_stable"

    one_token = to_wei(1, token["decimals"])
    q = await quote_provider.quote(token_symbol, stable, one_token)
    if not q.ok or q.amount_out_wei <= 0:
        return None, "infer_failed"

    stable_amt = from_wei(q.amount_out_wei, tokens[stable]["decimals"])
    return float(stable_amt), f"infer_via_{stable}"


async def infer_eth_usd(tokens: dict[str, Any], quote_provider, pricing_cfg: dict[str, Any]) -> tuple[float | None, str]:
    weth_sym = next((s for s, t in tokens.items() if s.upper() == "WETH"), None)
    if weth_sym:
        px, src = await infer_token_usd(
            token_symbol=weth_sym,
            tokens=tokens,
            quote_provider=quote_provider,
            mode="infer",
            static_prices=None,
        )
        if px is not None:
            return px, src

    static_eth = pricing_cfg.get("eth_usd_static")
    if static_eth is not None:
        return float(static_eth), "static"
    return None, "missing"


def estimate_amount_usd(amount_in_human: float, start_token: dict[str, Any], token_usd: float | None) -> float | None:
    if start_token.get("is_stable"):
        return float(amount_in_human)
    if token_usd is None:
        return None
    return float(Decimal(str(amount_in_human)) * Decimal(str(token_usd)))
