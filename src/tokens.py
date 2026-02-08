from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN, getcontext

getcontext().prec = 80


@dataclass(frozen=True)
class Token:
    symbol: str
    address: str
    decimals: int
    is_stable: bool = False
    static_price_usd: float | None = None


def to_wei(amount_human: float | str | Decimal, decimals: int) -> int:
    amount = Decimal(str(amount_human))
    scale = Decimal(10) ** decimals
    return int((amount * scale).quantize(Decimal("1"), rounding=ROUND_DOWN))


def from_wei(amount_wei: int, decimals: int) -> Decimal:
    scale = Decimal(10) ** decimals
    return Decimal(amount_wei) / scale
