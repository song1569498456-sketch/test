from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
from typing import Any

from web3 import Web3

from src.config_loader import load_config
from src.logger import JsonlLogger
from src.pricing.usd import estimate_amount_usd, infer_eth_usd, infer_token_usd
from src.quote.oneinch import OneInchQuoteProvider
from src.quote.uniswap_v3 import UniswapV3QuoteProvider
from src.routes.enumerate import enumerate_loops2, enumerate_triangles3
from src.tokens import from_wei, to_wei


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_provider(cfg: dict[str, Any], w3: Web3):
    if cfg["quote_source"] == "1inch":
        return OneInchQuoteProvider(cfg["chain_id"], cfg["tokens"], cfg["oneinch"])
    return UniswapV3QuoteProvider(w3, cfg["tokens"], cfg["uniswap"], cfg.get("min_pool_liquidity_usd"))


async def process_route(
    provider,
    cfg: dict[str, Any],
    w3: Web3,
    route_type: str,
    route: tuple[str, ...],
    amount_in_human: float,
) -> dict[str, Any]:
    tokens = cfg["tokens"]
    sanity_cfg = cfg["sanity"]
    max_jump = float(sanity_cfg.get("max_jump_ratio", 1000))

    start_symbol = route[0]
    start_token = tokens[start_symbol]
    amount_in_wei = to_wei(amount_in_human, start_token["decimals"])

    hops_symbols = []
    if route_type == "loop2":
        a, b = route
        hops_symbols = [(a, b), (b, a)]
        route_symbols = [a, b, a]
    else:
        a, b, c = route
        hops_symbols = [(a, b), (b, c), (c, a)]
        route_symbols = [a, b, c, a]

    flags = {
        "suspicious": False,
        "low_liquidity": False,
        "incomplete_pricing": False,
        "incomplete_pool_state": False,
    }

    hops = []
    current_in = amount_in_wei
    for token_in, token_out in hops_symbols:
        q = await provider.quote(token_in, token_out, current_in)
        if not q.ok or q.amount_out_wei <= 0:
            return {
                "ts_iso": now_iso(),
                "chainId": cfg["chain_id"],
                "source": cfg["quote_source"],
                "route_type": route_type,
                "route_symbols": route_symbols,
                "amount_in_human": amount_in_human,
                "amount_in_wei": str(amount_in_wei),
                "hops": hops,
                "gross_return_wei": "0",
                "gross_return_usd_est": None,
                "gas_price_wei": None,
                "gas_units_est": cfg["gas_units_estimate"][route_type],
                "gas_cost_usd_est": None,
                "buffer_bps": cfg["slippage_bps_buffer"],
                "buffer_usd_est": None,
                "net_usd_est": None,
                "flags": flags,
                "status": "error",
                "error_message": q.error or "quote_failed",
            }

        if sanity_cfg.get("enabled", True) and q.amount_out_wei > int(current_in * max_jump):
            flags["suspicious"] = True
            return {
                "ts_iso": now_iso(),
                "chainId": cfg["chain_id"],
                "source": cfg["quote_source"],
                "route_type": route_type,
                "route_symbols": route_symbols,
                "amount_in_human": amount_in_human,
                "amount_in_wei": str(amount_in_wei),
                "hops": hops,
                "gross_return_wei": "0",
                "gross_return_usd_est": None,
                "gas_price_wei": None,
                "gas_units_est": cfg["gas_units_estimate"][route_type],
                "gas_cost_usd_est": None,
                "buffer_bps": cfg["slippage_bps_buffer"],
                "buffer_usd_est": None,
                "net_usd_est": None,
                "flags": flags,
                "status": "error",
                "error_message": "suspicious_quote_jump",
            }

        if q.meta.get("pool_checks", {}).get("liquidity") == 0:
            flags["low_liquidity"] = True
        if q.meta.get("pool_checks", {}).get("incomplete_pool_state"):
            flags["incomplete_pool_state"] = True

        hops.append(
            {
                "token_in": token_in,
                "token_out": token_out,
                "amount_in_wei": str(current_in),
                "amount_out_wei": str(q.amount_out_wei),
                "quote_meta": q.meta,
            }
        )
        current_in = q.amount_out_wei

    gross_wei = current_in - amount_in_wei
    gross_human = from_wei(gross_wei, start_token["decimals"])

    token_usd, token_price_src = await infer_token_usd(
        start_symbol,
        tokens,
        provider,
        cfg["pricing"]["token_price_mode"],
        cfg["pricing"].get("static_prices", {}),
    )
    amount_usd = estimate_amount_usd(amount_in_human, start_token, token_usd)
    if amount_usd is None:
        flags["incomplete_pricing"] = True

    gross_usd = float(gross_human) if start_token["is_stable"] else (float(gross_human) * token_usd if token_usd is not None else None)

    if cfg.get("gas_price_gwei_override") is not None:
        gas_price_wei = int(float(cfg["gas_price_gwei_override"]) * 1e9)
    else:
        gas_price_wei = int(w3.eth.gas_price)

    eth_usd, eth_src = await infer_eth_usd(tokens, provider, cfg["pricing"])
    gas_units = cfg["gas_units_estimate"][route_type]
    gas_cost_usd = None
    if eth_usd is not None:
        gas_cost_usd = (gas_units * gas_price_wei * eth_usd) / 1e18
    else:
        flags["incomplete_pricing"] = True

    buffer_usd = None if amount_usd is None else amount_usd * (cfg["slippage_bps_buffer"] / 10000)

    net_usd = None
    if gross_usd is not None and gas_cost_usd is not None and buffer_usd is not None:
        net_usd = gross_usd - gas_cost_usd - buffer_usd

    return {
        "ts_iso": now_iso(),
        "chainId": cfg["chain_id"],
        "source": cfg["quote_source"],
        "route_type": route_type,
        "route_symbols": route_symbols,
        "amount_in_human": amount_in_human,
        "amount_in_wei": str(amount_in_wei),
        "hops": hops,
        "gross_return_wei": str(gross_wei),
        "gross_return_usd_est": gross_usd,
        "gas_price_wei": gas_price_wei,
        "gas_units_est": gas_units,
        "gas_cost_usd_est": gas_cost_usd,
        "buffer_bps": cfg["slippage_bps_buffer"],
        "buffer_usd_est": buffer_usd,
        "net_usd_est": net_usd,
        "flags": flags,
        "status": "ok",
        "error_message": None,
        "price_source": {"token_usd": token_price_src, "eth_usd": eth_src},
    }


async def run(config_path: str) -> None:
    cfg = load_config(config_path)
    w3 = Web3(Web3.HTTPProvider(cfg["rpc_url"]))
    provider = build_provider(cfg, w3)
    logger = JsonlLogger("logs")
    sem = asyncio.Semaphore(cfg["max_concurrency"])

    loops2 = enumerate_loops2(cfg)
    triangles3 = enumerate_triangles3(cfg)

    async def bounded(route_type: str, route: tuple[str, ...], amount_in_human: float):
        async with sem:
            return await process_route(provider, cfg, w3, route_type, route, amount_in_human)

    try:
        while True:
            tasks = []
            for route in loops2:
                sym = route[0]
                for amt in cfg["amounts"].get(sym, []):
                    tasks.append(asyncio.create_task(bounded("loop2", route, float(amt))))

            for route in triangles3:
                sym = route[0]
                for amt in cfg["amounts"].get(sym, []):
                    tasks.append(asyncio.create_task(bounded("triangle3", route, float(amt))))

            results = await asyncio.gather(*tasks, return_exceptions=False)
            for row in results:
                logger.write(row)

            ranked = sorted(
                [r for r in results if r.get("net_usd_est") is not None],
                key=lambda x: x["net_usd_est"],
                reverse=True,
            )
            print(f"[{now_iso()}] top {cfg['top_n']} opportunities")
            for r in ranked[: cfg["top_n"]]:
                print(
                    f"{r['route_type']} {r['route_symbols']} in={r['amount_in_human']} net_usd={r['net_usd_est']:.6f} gross_usd={r['gross_return_usd_est']}"
                )
            await asyncio.sleep(float(cfg["loop_interval_sec"]))
    finally:
        if isinstance(provider, OneInchQuoteProvider):
            await provider.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Dry-run DEX quote collector")
    parser.add_argument("--config", required=True, help="Path to YAML/JSON config")
    args = parser.parse_args()
    asyncio.run(run(args.config))


if __name__ == "__main__":
    main()
