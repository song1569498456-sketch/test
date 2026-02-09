from __future__ import annotations

import asyncio
import math

from src.main import process_route
from src.quote.base import QuoteResult
from src.tokens import to_wei

from tests.fakes import FakeQuoteProvider, FakeWeb3


def _base_cfg() -> dict:
    return {
        "chain_id": 8453,
        "quote_source": "uniswap",
        "tokens": {
            "USDC": {"symbol": "USDC", "address": "0x1", "decimals": 6, "is_stable": True},
            "WETH": {"symbol": "WETH", "address": "0x2", "decimals": 18, "is_stable": False},
        },
        "sanity": {"enabled": False, "max_jump_ratio": 1000},
        "pricing": {"token_price_mode": "static", "static_prices": {"WETH": 3000}, "eth_usd_static": 3000},
        "gas_units_estimate": {"loop2": 180000, "triangle3": 260000},
        "slippage_bps_buffer": 10,
        "gas_price_gwei_override": 10,
    }


def test_process_route_ok_path_loop2() -> None:
    cfg = _base_cfg()
    amount_in = 100.0
    amount_usdc_in = to_wei(amount_in, 6)
    amount_weth_out = int(0.0335 * 10**18)
    amount_usdc_back = to_wei(101, 6)

    provider = FakeQuoteProvider(
        {
            ("USDC", "WETH", amount_usdc_in): QuoteResult(True, amount_usdc_in, amount_weth_out, "USDC", "WETH"),
            ("WETH", "USDC", amount_weth_out): QuoteResult(True, amount_weth_out, amount_usdc_back, "WETH", "USDC"),
            ("WETH", "USDC", 10**18): QuoteResult(True, 10**18, to_wei(3000, 6), "WETH", "USDC"),
        }
    )

    result = asyncio.run(process_route(provider, cfg, FakeWeb3(10_000_000_000), "loop2", ("USDC", "WETH"), amount_in))

    assert result["status"] == "ok"
    assert result["error_message"] is None
    assert result["flags"]["suspicious"] is False
    assert result["net_usd_est"] is not None

    expected_net = result["gross_return_usd_est"] - result["gas_cost_usd_est"] - result["buffer_usd_est"]
    assert math.isclose(result["net_usd_est"], expected_net, rel_tol=0, abs_tol=1e-9)


def test_process_route_quote_failed_returns_error() -> None:
    cfg = _base_cfg()
    amount_usdc_in = to_wei(100, 6)
    amount_weth_out = int(0.0335 * 10**18)

    provider = FakeQuoteProvider(
        {
            ("USDC", "WETH", amount_usdc_in): QuoteResult(True, amount_usdc_in, amount_weth_out, "USDC", "WETH"),
            ("WETH", "USDC", amount_weth_out): QuoteResult(False, amount_weth_out, 0, "WETH", "USDC", error="upstream_timeout"),
        }
    )

    result = asyncio.run(process_route(provider, cfg, FakeWeb3(10_000_000_000), "loop2", ("USDC", "WETH"), 100.0))

    assert result["status"] == "error"
    assert result["error_message"] == "upstream_timeout"
    assert result["net_usd_est"] is None
    assert len(result["hops"]) == 1


def test_process_route_suspicious_jump_flagged() -> None:
    cfg = _base_cfg()
    cfg["sanity"]["enabled"] = True
    cfg["sanity"]["max_jump_ratio"] = 2

    amount_usdc_in = to_wei(100, 6)
    suspicious_out = amount_usdc_in * 3
    provider = FakeQuoteProvider(
        {
            ("USDC", "WETH", amount_usdc_in): QuoteResult(True, amount_usdc_in, suspicious_out, "USDC", "WETH"),
        }
    )

    result = asyncio.run(process_route(provider, cfg, FakeWeb3(10_000_000_000), "loop2", ("USDC", "WETH"), 100.0))

    assert result["status"] == "error"
    assert result["flags"]["suspicious"] is True
    assert result["error_message"] == "suspicious_quote_jump"


def test_process_route_marks_low_liquidity_and_incomplete_pool_state() -> None:
    cfg = _base_cfg()
    amount_usdc_in = to_wei(100, 6)
    amount_weth_out = int(0.0335 * 10**18)
    amount_usdc_back = to_wei(99, 6)

    provider = FakeQuoteProvider(
        {
            (
                "USDC",
                "WETH",
                amount_usdc_in,
            ): QuoteResult(
                True,
                amount_usdc_in,
                amount_weth_out,
                "USDC",
                "WETH",
                meta={"pool_checks": {"liquidity": 0, "incomplete_pool_state": True}},
            ),
            ("WETH", "USDC", amount_weth_out): QuoteResult(True, amount_weth_out, amount_usdc_back, "WETH", "USDC"),
            ("WETH", "USDC", 10**18): QuoteResult(True, 10**18, to_wei(3000, 6), "WETH", "USDC"),
        }
    )

    result = asyncio.run(process_route(provider, cfg, FakeWeb3(10_000_000_000), "loop2", ("USDC", "WETH"), 100.0))

    assert result["status"] == "ok"
    assert result["flags"]["low_liquidity"] is True
    assert result["flags"]["incomplete_pool_state"] is True
