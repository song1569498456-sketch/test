# 最小可落地计划：先保证“持续产出可信套利评估结果”

## 1) 优先级结论（P0 / P1 / P2）

- **P0：把 `process_route` 变成可稳定验证的核心判定单元 + 最小业务结果测试集。**  
  必要性：当前所有关键业务字段（`status`/`flags`/`net_usd_est`/`error_message`）都在 `src/main.py:process_route` 聚合，若不先锁定这里，输出可信度无从谈起。
- **P1：建立配置校验失败的“快速失败”测试，防止错误配置导致持续产出垃圾结果。**  
  必要性：框架持续运行依赖配置，配置错了会导致系统稳定地产出错误结论。
- **P2：一键执行（本地+CI）与可复现策略（固定 fake 输入 + 固定 gas/price）。**  
  必要性：没有统一入口和固定输入，结果不可复验，无法“被信赖”。

## 2) 最小测试集清单（按文件）

### `tests/test_process_route_minimal.py`
- `test_process_route_ok_path_loop2`  
  验证真实风险：**正常报价链路下净收益计算错误**（`net_usd_est` 算错会直接误导是否套利）。
- `test_process_route_quote_failed_returns_error`  
  验证真实风险：**任一 hop 报价失败未正确失败**（可能把失败当盈利机会）。
- `test_process_route_suspicious_jump_flagged`  
  验证真实风险：**异常跳价未被拦截**（脏数据进入机会池）。
- `test_process_route_marks_low_liquidity_and_incomplete_pool_state`  
  验证真实风险：**低流动性/池状态不完整未标记**（结果可执行性被高估）。

### `tests/test_config_loader_minimal.py`
- `test_validate_config_rejects_missing_required_keys`  
  验证真实风险：**关键配置缺失仍启动**（持续输出不可用结果）。
- `test_validate_config_rejects_invalid_quote_source`  
  验证真实风险：**非法报价源导致运行期不确定行为**。

### `tests/fakes.py`
- `FakeQuoteProvider` / `FakeWeb3`（仅测试用）  
  验证真实风险：**测试依赖外部链路导致不稳定**。使用 fake 固定输入保证每次结论一致。

## 3) 测试用例输入 / 期望输出（覆盖 4 类场景）

### A. 正常路径（ok）
- 输入：
  - route: `("USDC", "WETH")`, route_type=`loop2`, amount_in_human=`100`
  - Fake hop1: `100 USDC -> 0.0335 WETH`
  - Fake hop2: `0.0335 WETH -> 101 USDC`
  - `gas_price_gwei_override=10`, `eth_usd_static=3000`, `slippage_bps_buffer=10`
- 期望输出：
  - `status == "ok"`
  - `error_message is None`
  - `flags.suspicious == False`
  - `net_usd_est` 为可计算数值且与公式一致：`gross_usd - gas_cost_usd_est - buffer_usd_est`
- 为什么必要：直接验证“机会评估结果是否可用且可解释”。

### B. 报价失败（quote failed）
- 输入：第 2 跳返回 `QuoteResult(ok=False, error="upstream_timeout")`
- 期望输出：
  - `status == "error"`
  - `error_message == "upstream_timeout"`
  - `net_usd_est is None`
  - `hops` 仅保留已成功 hop
- 为什么必要：防止失败路径被误当成机会。

### C. suspicious jump
- 输入：`sanity.enabled=True`, `max_jump_ratio=2`；某 hop `amount_out_wei > current_in * 2`
- 期望输出：
  - `status == "error"`
  - `flags.suspicious == True`
  - `error_message == "suspicious_quote_jump"`
- 为什么必要：拦截异常数据，提升可信度下限。

### D. 配置错误（config invalid）
- 输入：缺失 `gas_units_estimate` 或 `quote_source="foo"`
- 期望输出：
  - 抛出 `ConfigError`
  - 错误信息包含对应缺失/非法字段
- 为什么必要：将错误前置到启动阶段，避免在线上循环产生错误输出。

## 4) 必要代码改动清单（必须 / 可选）

### 必须
1. **新增 `tests/fakes.py`**（FakeQuoteProvider、FakeWeb3）  
   - 为什么必须：满足“mock/fake provider，避免真实链/API”，保证稳定与可复现。
2. **新增 `tests/test_process_route_minimal.py`**（4 个业务结果断言）  
   - 为什么必须：直接覆盖核心业务字段，映射真实功能效果。
3. **新增 `tests/test_config_loader_minimal.py`**（配置快速失败）  
   - 为什么必须：避免错误配置造成持续错误产出。
4. **`requirements.txt` 增加 `pytest`**  
   - 为什么必须：提供统一、最小可执行测试入口。
5. **新增 `Makefile`（`make test`）**  
   - 为什么必须：实现“一键执行 + 自动校验”。

### 可选
1. **`src/main.py` 小幅重构：抽出结果组装函数（如 `_error_result`）**  
   - 为什么可选：降低重复字典拼装，减少维护风险；但不影响最小可落地。
2. **`pytest.ini` 固定 `-q --disable-warnings`**  
   - 为什么可选：提升输出可读性，不影响正确性。

## 5) 一键执行方案（本地 / CI / 失败判定 / 可复现）

- 本地命令：
  1. `python -m venv .venv && source .venv/bin/activate`
  2. `pip install -r requirements.txt`
  3. `make test`
- CI 命令（GitHub Actions 单 job 即可）：
  - `pip install -r requirements.txt && make test`
- 失败判定标准：
  - 任一测试失败、报错、或进程退出码非 0 => **判定失败**。
- 可复现策略：
  - 所有测试仅使用 `tests/fakes.py`，不访问 RPC / 1inch。
  - 用固定输入、固定 gas（`gas_price_gwei_override`）、固定价格（`eth_usd_static`）保证数值可重复。
  - 对 `net_usd_est` 使用明确公式断言（可设置容差 `abs_tol=1e-9`）。

## 6) 完成定义 DoD（客观验收 checklist）

- [ ] `tests/test_process_route_minimal.py` 覆盖正常/报价失败/suspicious jump，且断言 `status/flags/net_usd_est/error_message`。
- [ ] `tests/test_config_loader_minimal.py` 覆盖配置缺失与非法 `quote_source`。
- [ ] 测试运行不依赖外部网络，不调用真实 RPC / 外部 API。
- [ ] 本地执行 `make test` 返回 0。
- [ ] CI 中执行同一命令返回 0。
- [ ] 同一提交重复执行测试，结果一致（通过数与关键断言一致）。
