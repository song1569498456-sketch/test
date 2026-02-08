from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml


REQUIRED_TOP_LEVEL = {
    "rpc_url",
    "chain_id",
    "quote_source",
    "tokens",
    "route_sets",
    "amounts",
    "loop_interval_sec",
    "slippage_bps_buffer",
    "gas_units_estimate",
    "path_enum_rules",
}


class ConfigError(ValueError):
    pass


def _load_raw(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        return yaml.safe_load(text)
    if path.suffix.lower() == ".json":
        return json.loads(text)
    raise ConfigError("Config file must be YAML or JSON")


def validate_config(cfg: dict[str, Any]) -> dict[str, Any]:
    missing = REQUIRED_TOP_LEVEL - set(cfg)
    if missing:
        raise ConfigError(f"Missing required config keys: {sorted(missing)}")

    if cfg["quote_source"] not in {"1inch", "uniswap"}:
        raise ConfigError("quote_source must be '1inch' or 'uniswap'")

    if not isinstance(cfg["tokens"], dict) or not cfg["tokens"]:
        raise ConfigError("tokens must be a non-empty map")

    for symbol, token in cfg["tokens"].items():
        for field in ["symbol", "address", "decimals", "is_stable"]:
            if field not in token:
                raise ConfigError(f"token {symbol} missing field: {field}")

    route_sets = cfg["route_sets"]
    if "loops2" not in route_sets or "triangles3" not in route_sets:
        raise ConfigError("route_sets must contain loops2 and triangles3")

    gas_units = cfg["gas_units_estimate"]
    if "loop2" not in gas_units or "triangle3" not in gas_units:
        raise ConfigError("gas_units_estimate must contain loop2 and triangle3")

    cfg.setdefault("oneinch", {})
    cfg.setdefault("pricing", {})
    cfg.setdefault("min_pool_liquidity_usd", None)
    cfg.setdefault("top_n", 10)
    cfg.setdefault("max_concurrency", 8)
    cfg.setdefault("uniswap", {})
    cfg.setdefault("sanity", {})

    cfg["sanity"].setdefault("enabled", True)
    cfg["sanity"].setdefault("max_jump_ratio", 1000)

    pricing = cfg["pricing"]
    pricing.setdefault("token_price_mode", "infer")
    pricing.setdefault("eth_usd_static", None)

    oneinch = cfg["oneinch"]
    oneinch.setdefault("base_url", "https://api.1inch.dev/swap/v6.0")
    oneinch.setdefault("api_key", "")
    oneinch.setdefault("timeout_sec", 8)
    oneinch.setdefault("max_retries", 4)

    uni = cfg["uniswap"]
    uni.setdefault("factory_address", "")
    uni.setdefault("quoter_v2_address", "")
    uni.setdefault("quoter_address", "")
    uni.setdefault("check_pool_state", True)

    return cfg


def load_config(path: str) -> dict[str, Any]:
    cfg = _load_raw(Path(path))
    return validate_config(cfg)
