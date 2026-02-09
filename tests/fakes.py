from __future__ import annotations

from dataclasses import dataclass

from src.quote.base import QuoteResult


@dataclass
class _Eth:
    gas_price: int


class FakeWeb3:
    def __init__(self, gas_price_wei: int):
        self.eth = _Eth(gas_price_wei)


class FakeQuoteProvider:
    """Deterministic async quote provider for tests."""

    def __init__(self, responses: dict[tuple[str, str, int], QuoteResult]):
        self.responses = responses

    async def quote(self, token_in: str, token_out: str, amount_in_wei: int) -> QuoteResult:
        key = (token_in, token_out, amount_in_wei)
        result = self.responses.get(key)
        if result is not None:
            return result
        return QuoteResult(
            ok=False,
            amount_in_wei=amount_in_wei,
            amount_out_wei=0,
            token_in=token_in,
            token_out=token_out,
            error="missing_fake_quote",
        )
