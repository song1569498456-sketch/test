from __future__ import annotations

import pytest

from src.config_loader import ConfigError, validate_config


def _valid_cfg() -> dict:
    return {
        "rpc_url": "http://localhost:8545",
        "chain_id": 1,
        "quote_source": "uniswap",
        "tokens": {
            "USDC": {"symbol": "USDC", "address": "0x1", "decimals": 6, "is_stable": True},
            "WETH": {"symbol": "WETH", "address": "0x2", "decimals": 18, "is_stable": False},
        },
        "route_sets": {"loops2": [["USDC", "WETH"]], "triangles3": [["USDC", "WETH", "USDC"]]},
        "amounts": {"USDC": [100]},
        "loop_interval_sec": 1,
        "slippage_bps_buffer": 10,
        "gas_units_estimate": {"loop2": 180000, "triangle3": 260000},
        "path_enum_rules": {
            "triangle_only_if_all_tokens_whitelisted": True,
            "max_triangles_per_base_token": 50,
            "dedup_by_sorted_symbols": True,
        },
    }


def test_validate_config_rejects_missing_required_keys() -> None:
    cfg = _valid_cfg()
    cfg.pop("gas_units_estimate")

    with pytest.raises(ConfigError, match="Missing required config keys"):
        validate_config(cfg)


def test_validate_config_rejects_invalid_quote_source() -> None:
    cfg = _valid_cfg()
    cfg["quote_source"] = "foo"

    with pytest.raises(ConfigError, match="quote_source must be '1inch' or 'uniswap'"):
        validate_config(cfg)
