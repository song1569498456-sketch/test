from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml


CHAIN_PRESETS: dict[str, dict[str, Any]] = {
    "base": {
        "chain_id": 8453,
        "tokens": {
            "USDC": {"address": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", "decimals": 6, "is_stable": True},
            "WETH": {"address": "0x4200000000000000000000000000000000000006", "decimals": 18, "is_stable": False},
            "DAI": {"address": "0x50c5725949A6F0c72E6C4a641F24049A917DB0Cb", "decimals": 18, "is_stable": True},
        },
    },
    "ethereum": {
        "chain_id": 1,
        "tokens": {
            "USDC": {"address": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", "decimals": 6, "is_stable": True},
            "WETH": {"address": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2", "decimals": 18, "is_stable": False},
            "DAI": {"address": "0x6B175474E89094C44Da98b954EedeAC495271d0F", "decimals": 18, "is_stable": True},
        },
    },
}

UNISWAP_V3_COMMON = {
    "factory_address": "0x1F98431c8aD98523631AE4a59f267346ea31F984",
    "quoter_v2_address": "0x61fFE014bA17989E743c5F6cB21bF9697530B21e",
    "quoter_address": "0xb27308f9F90D607463bb33eA1BeBb41C27CE5AB6",
    "check_pool_state": True,
}


def build_config(chain: str, quote_source: str, rpc_url: str, oneinch_api_key: str = "") -> dict[str, Any]:
    if chain not in CHAIN_PRESETS:
        raise ValueError(f"Unsupported chain preset: {chain}")

    preset = CHAIN_PRESETS[chain]
    chain_id = preset["chain_id"]

    tokens = {
        symbol: {
            "symbol": symbol,
            "address": info["address"],
            "decimals": info["decimals"],
            "is_stable": info["is_stable"],
        }
        for symbol, info in preset["tokens"].items()
    }

    cfg: dict[str, Any] = {
        "rpc_url": rpc_url,
        "chain_id": chain_id,
        "quote_source": quote_source,
        "tokens": tokens,
        "route_sets": {
            "loops2": [["USDC", "WETH"], ["USDC", "DAI"]],
            "triangles3": [["USDC", "WETH", "DAI"]],
        },
        "amounts": {"USDC": [10, 20, 50], "DAI": [10, 50]},
        "loop_interval_sec": 2,
        "slippage_bps_buffer": 10,
        "gas_units_estimate": {"loop2": 180000, "triangle3": 260000},
        "gas_price_gwei_override": None,
        "min_pool_liquidity_usd": 20000,
        "path_enum_rules": {
            "triangle_only_if_all_tokens_whitelisted": True,
            "max_triangles_per_base_token": 50,
            "dedup_by_sorted_symbols": True,
        },
        "oneinch": {
            "base_url": "https://api.1inch.dev/swap/v6.0",
            "api_key": oneinch_api_key,
            "timeout_sec": 8,
            "max_retries": 4,
        },
        "uniswap": dict(UNISWAP_V3_COMMON),
        "pricing": {"token_price_mode": "infer", "static_prices": {"WETH": 3000}, "eth_usd_static": 3000},
        "sanity": {"enabled": True, "max_jump_ratio": 1000},
        "top_n": 10,
        "max_concurrency": 8,
    }
    return cfg


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate starter config.yaml with known token/router presets")
    parser.add_argument("--chain", choices=sorted(CHAIN_PRESETS.keys()), default="base")
    parser.add_argument("--quote-source", choices=["1inch", "uniswap"], default="1inch")
    parser.add_argument("--rpc-url", required=True, help="RPC endpoint URL from your node provider")
    parser.add_argument("--oneinch-api-key", default="", help="Optional 1inch API key")
    parser.add_argument("--out", default="config.generated.yaml", help="Output file path")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cfg = build_config(args.chain, args.quote_source, args.rpc_url, args.oneinch_api_key)
    out = Path(args.out)
    out.write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True), encoding="utf-8")
    print(f"Wrote config to: {out}")
    print("Next step: verify rpc_url works, then run: python -m src.main --config", out)


if __name__ == "__main__":
    main()
