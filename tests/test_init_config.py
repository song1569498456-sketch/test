from __future__ import annotations

import pytest

from src.tools.init_config import build_config


def test_build_config_fills_known_base_tokens() -> None:
    cfg = build_config(chain="base", quote_source="1inch", rpc_url="https://example-rpc")

    assert cfg["chain_id"] == 8453
    assert cfg["tokens"]["USDC"]["address"] == "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
    assert cfg["tokens"]["WETH"]["address"] == "0x4200000000000000000000000000000000000006"
    assert cfg["uniswap"]["factory_address"] == "0x1F98431c8aD98523631AE4a59f267346ea31F984"


def test_build_config_rejects_unknown_chain() -> None:
    with pytest.raises(ValueError, match="Unsupported chain preset"):
        build_config(chain="unknown", quote_source="1inch", rpc_url="https://example-rpc")
