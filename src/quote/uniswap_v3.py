from __future__ import annotations

from typing import Any

from web3 import Web3

from src.quote.base import QuoteResult

FACTORY_ABI = [
    {
        "inputs": [
            {"internalType": "address", "name": "tokenA", "type": "address"},
            {"internalType": "address", "name": "tokenB", "type": "address"},
            {"internalType": "uint24", "name": "fee", "type": "uint24"},
        ],
        "name": "getPool",
        "outputs": [{"internalType": "address", "name": "pool", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    }
]

POOL_ABI = [
    {
        "inputs": [],
        "name": "slot0",
        "outputs": [
            {"internalType": "uint160", "name": "sqrtPriceX96", "type": "uint160"},
            {"internalType": "int24", "name": "tick", "type": "int24"},
            {"internalType": "uint16", "name": "observationIndex", "type": "uint16"},
            {"internalType": "uint16", "name": "observationCardinality", "type": "uint16"},
            {"internalType": "uint16", "name": "observationCardinalityNext", "type": "uint16"},
            {"internalType": "uint8", "name": "feeProtocol", "type": "uint8"},
            {"internalType": "bool", "name": "unlocked", "type": "bool"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "liquidity",
        "outputs": [{"internalType": "uint128", "name": "", "type": "uint128"}],
        "stateMutability": "view",
        "type": "function",
    },
]

QUOTER_V2_ABI = [
    {
        "inputs": [
            {
                "components": [
                    {"internalType": "address", "name": "tokenIn", "type": "address"},
                    {"internalType": "address", "name": "tokenOut", "type": "address"},
                    {"internalType": "uint24", "name": "fee", "type": "uint24"},
                    {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
                    {"internalType": "uint160", "name": "sqrtPriceLimitX96", "type": "uint160"},
                ],
                "internalType": "struct IQuoterV2.QuoteExactInputSingleParams",
                "name": "params",
                "type": "tuple",
            }
        ],
        "name": "quoteExactInputSingle",
        "outputs": [
            {"internalType": "uint256", "name": "amountOut", "type": "uint256"},
            {"internalType": "uint160", "name": "sqrtPriceX96After", "type": "uint160"},
            {"internalType": "uint32", "name": "initializedTicksCrossed", "type": "uint32"},
            {"internalType": "uint256", "name": "gasEstimate", "type": "uint256"},
        ],
        "stateMutability": "nonpayable",
        "type": "function",
    }
]

QUOTER_ABI = [
    {
        "inputs": [
            {"internalType": "address", "name": "tokenIn", "type": "address"},
            {"internalType": "address", "name": "tokenOut", "type": "address"},
            {"internalType": "uint24", "name": "fee", "type": "uint24"},
            {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
            {"internalType": "uint160", "name": "sqrtPriceLimitX96", "type": "uint160"},
        ],
        "name": "quoteExactInputSingle",
        "outputs": [{"internalType": "uint256", "name": "amountOut", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function",
    }
]


class UniswapV3QuoteProvider:
    def __init__(self, w3: Web3, tokens: dict[str, Any], cfg: dict[str, Any], min_pool_liquidity_usd: float | None = None) -> None:
        self.w3 = w3
        self.tokens = tokens
        self.factory = w3.eth.contract(address=Web3.to_checksum_address(cfg["factory_address"]), abi=FACTORY_ABI)
        self.quoter_v2 = w3.eth.contract(address=Web3.to_checksum_address(cfg["quoter_v2_address"]), abi=QUOTER_V2_ABI)
        self.quoter = w3.eth.contract(address=Web3.to_checksum_address(cfg["quoter_address"]), abi=QUOTER_ABI)
        self.fees = [500, 3000, 10000]
        self.check_pool_state = cfg.get("check_pool_state", True)
        self.min_pool_liquidity_usd = min_pool_liquidity_usd

    def _get_pool(self, token_in: str, token_out: str, fee: int) -> str:
        a = Web3.to_checksum_address(self.tokens[token_in]["address"])
        b = Web3.to_checksum_address(self.tokens[token_out]["address"])
        return self.factory.functions.getPool(a, b, fee).call()

    def _pool_state(self, pool_address: str) -> tuple[bool, int | None]:
        pool = self.w3.eth.contract(address=Web3.to_checksum_address(pool_address), abi=POOL_ABI)
        slot0_ok = False
        liq = None
        try:
            pool.functions.slot0().call()
            slot0_ok = True
        except Exception:  # noqa: BLE001
            slot0_ok = False
        try:
            liq = int(pool.functions.liquidity().call())
        except Exception:  # noqa: BLE001
            liq = None
        return slot0_ok, liq

    def _quote_one(self, token_in: str, token_out: str, amount_in_wei: int, fee: int) -> tuple[int, str, dict[str, Any], str | None]:
        pool_address = self._get_pool(token_in, token_out, fee)
        if int(pool_address, 16) == 0:
            return 0, "", {"exists": False, "liquidity": None, "slot0_ok": False}, "pool_not_found"

        slot0_ok = False
        liq = None
        incomplete_pool_state = False
        if self.check_pool_state:
            slot0_ok, liq = self._pool_state(pool_address)
            if liq is None or not slot0_ok:
                incomplete_pool_state = True

        if self.min_pool_liquidity_usd is not None and liq is not None and liq < int(self.min_pool_liquidity_usd):
            return 0, pool_address, {"exists": True, "liquidity": liq, "slot0_ok": slot0_ok, "incomplete_pool_state": incomplete_pool_state}, "low_liquidity"

        a = Web3.to_checksum_address(self.tokens[token_in]["address"])
        b = Web3.to_checksum_address(self.tokens[token_out]["address"])

        try:
            params = (a, b, fee, amount_in_wei, 0)
            amount_out, _, _, gas_estimate = self.quoter_v2.functions.quoteExactInputSingle(params).call()
            return int(amount_out), pool_address, {
                "exists": True,
                "liquidity": liq,
                "slot0_ok": slot0_ok,
                "incomplete_pool_state": incomplete_pool_state,
                "gasEstimate": int(gas_estimate),
            }, "QuoterV2"
        except Exception:  # noqa: BLE001
            try:
                amount_out = self.quoter.functions.quoteExactInputSingle(a, b, fee, amount_in_wei, 0).call()
                return int(amount_out), pool_address, {
                    "exists": True,
                    "liquidity": liq,
                    "slot0_ok": slot0_ok,
                    "incomplete_pool_state": incomplete_pool_state,
                }, "Quoter"
            except Exception as exc:  # noqa: BLE001
                return 0, pool_address, {"exists": True, "liquidity": liq, "slot0_ok": slot0_ok, "incomplete_pool_state": incomplete_pool_state}, str(exc)

    async def quote(self, token_in: str, token_out: str, amount_in_wei: int) -> QuoteResult:
        best_out = 0
        best_meta: dict[str, Any] = {}
        best_err = None

        for fee in self.fees:
            out, pool_addr, checks, quoter_used = self._quote_one(token_in, token_out, amount_in_wei, fee)
            if out > best_out:
                best_out = out
                best_meta = {
                    "fee_tier_used": fee,
                    "pool_address": pool_addr,
                    "quoter_used": quoter_used if quoter_used in {"QuoterV2", "Quoter"} else None,
                    "pool_checks": checks,
                }
            if out == 0 and isinstance(quoter_used, str) and quoter_used not in {"QuoterV2", "Quoter"}:
                best_err = quoter_used

        return QuoteResult(
            ok=best_out > 0,
            amount_in_wei=amount_in_wei,
            amount_out_wei=best_out,
            token_in=token_in,
            token_out=token_out,
            meta=best_meta,
            error=None if best_out > 0 else (best_err or "no_viable_fee_tier"),
        )
