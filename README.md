# EVM DEX Dry-Run Quoter (Quote Only, No Trading)

Python 3.10+ 原型：只做报价和收益估计，不签名、不发送交易、不读取私钥。

支持：
- 2-hop 循环：`A -> B -> A`
- 3-hop 三角：`A -> B -> C -> A`

报价源（可切换）：
- `1inch` Classic Swap Quote API
- `uniswap` V3 QuoterV2（失败回退 Quoter）

## 安装

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 配置

创建 `config.yaml`（示例）：

```yaml
rpc_url: "https://base-mainnet.g.alchemy.com/v2/<YOUR_KEY>"
chain_id: 8453
quote_source: "1inch" # or "uniswap"

tokens:
  USDC:
    symbol: "USDC"
    address: "<USDC_ADDR>"
    decimals: 6
    is_stable: true
  WETH:
    symbol: "WETH"
    address: "<WETH_ADDR>"
    decimals: 18
    is_stable: false
    static_price_usd: 3000
  DAI:
    symbol: "DAI"
    address: "<DAI_ADDR>"
    decimals: 18
    is_stable: true

route_sets:
  loops2:
    - ["USDC", "WETH"]
    - ["USDC", "DAI"]
  triangles3:
    - ["USDC", "WETH", "DAI"]

amounts:
  USDC: [10, 20, 50, 100]
  DAI: [10, 50, 100]

loop_interval_sec: 2
slippage_bps_buffer: 10

gas_units_estimate:
  loop2: 180000
  triangle3: 260000

gas_price_gwei_override: null
min_pool_liquidity_usd: 20000

path_enum_rules:
  triangle_only_if_all_tokens_whitelisted: true
  max_triangles_per_base_token: 50
  dedup_by_sorted_symbols: true

oneinch:
  base_url: "https://api.1inch.dev/swap/v6.0"
  api_key: ""
  timeout_sec: 8
  max_retries: 4

uniswap:
  factory_address: "<UNISWAP_V3_FACTORY_ADDR>"
  quoter_v2_address: "<UNISWAP_V3_QUOTER_V2_ADDR>"
  quoter_address: "<UNISWAP_V3_QUOTER_ADDR>"
  check_pool_state: true

pricing:
  token_price_mode: "infer" # infer | static
  static_prices:
    WETH: 3000
  eth_usd_static: 3000

sanity:
  enabled: true
  max_jump_ratio: 1000

top_n: 10
max_concurrency: 8
```

## 快速生成可用配置（推荐）

如果你不知道 `rpc_url`、token 地址怎么填，可以先用内置脚本生成：

```bash
python -m src.tools.init_config --chain base --quote-source 1inch --rpc-url "https://<provider-endpoint>" --out config.generated.yaml
```

可选参数：
- `--chain`: `base` / `ethereum`
- `--quote-source`: `1inch` / `uniswap`
- `--oneinch-api-key`: 可选，1inch API key

脚本会自动填充常用 token 地址（USDC/WETH/DAI）与 Uniswap V3 factory/quoter 地址，你只需要提供 RPC URL。

### 什么是 RPC URL / key？

- `rpc_url`：访问链上节点的 HTTP 地址（例如 Alchemy、Infura、Ankr、QuickNode 提供）。
- `<YOUR_KEY>`：通常是节点服务商给你的 API Key，拼在 URL 里用于鉴权。
- 你可以先注册任一节点服务商，创建 Base 或 Ethereum 主网应用，然后复制它给你的 HTTPS endpoint 填到 `--rpc-url`。

## 运行

```bash
python -m src.main --config config.yaml
```

## 输出

- 控制台：每轮按 `net_usd_est` 降序输出 Top N。
- 日志：`logs/YYYYMMDD.jsonl`，每行一个 JSON，包含 hops、报价元数据、收益估计、flags、错误信息等。

JSONL 字段包括：
- `ts_iso`, `chainId`, `source`, `route_type`, `route_symbols`
- `amount_in_human`, `amount_in_wei`, `hops`
- `gross_return_wei`, `gross_return_usd_est`
- `gas_price_wei`, `gas_units_est`, `gas_cost_usd_est`
- `buffer_bps`, `buffer_usd_est`, `net_usd_est`
- `flags`, `status`, `error_message`

## 说明

- 1inch 请求包含重试（429/5xx 指数退避 + 抖动）与超时控制。
- Uniswap 对 fee tiers `[500, 3000, 10000]` 全部尝试并选择最大 `amount_out`。
- 仅 `eth_call` 报价；不含 `send_raw_transaction` / `sign_transaction`。
