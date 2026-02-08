from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class QuoteResult:
    ok: bool
    amount_in_wei: int
    amount_out_wei: int
    token_in: str
    token_out: str
    meta: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class QuoteProvider(Protocol):
    async def quote(self, token_in: str, token_out: str, amount_in_wei: int) -> QuoteResult: ...
