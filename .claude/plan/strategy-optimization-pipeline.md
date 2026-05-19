# Plan: 策略優化 Pipeline

**目標**：在接實盤之前，建立一套可靠的統計式參數優化→自動應用循環。

**用戶設計決策（已確認）**：
- AI 核心 = 統計式（回測找最佳參數）
- 多策略同幣種 = 刻意獨立運作，不互斥
- 優先順序 = 策略優化到滿意 → 接實盤

---

## 現狀盤點

### 已知 Bug（必修）

| 檔案 | 行號 | 問題 |
|------|------|------|
| `multi_segment_param_search.py` | L95 | `summary_df` 未定義（應為 `pd.DataFrame(all_summary)`），程式執行到這行必然 crash |

### 結構性缺陷

1. **最佳化指標只看 PnL** — 高 PnL 可能只是幾筆大單撐起來，不代表策略穩定。需加入 Sharpe、最大回撤。

2. **搜尋空間過窄** — 目前只搜 `tp_r` × `tol_fvg`，`lookback`（固定=3）和 `ab_level_threshold`（固定=0.01）也是敏感參數但沒有搜尋。

3. **分級（A/AB/B/C）沒有分別統計** — 不知道哪個級別真的賺錢，無法精準決定要不要開放 C 級進場。

4. **回測 vs 實盤策略不一致** —
   - `param_search.py` / `multi_segment_param_search.py` 使用 `strategy.py` 的 `SMCStrategy` / `SMCStrategyLoose`（與實盤相同 ✓）
   - `backtest.py` 使用 `strategy_periodic.py` 的 `FiveMinStrategy` 等（不同 class，回測結果無法直接對應實盤）

5. **最佳參數沒有自動寫回 config** — Walk-forward 跑完要手動抄參數到 `config.py`，容易漏。

---

## 實作計畫

### Step 1：修 `multi_segment_param_search.py` 的 crash bug
**改動**：L95 `summary_df.to_csv(...)` 前補上 `summary_df = pd.DataFrame(all_summary)`
**驗證**：執行腳本不再 crash，總績效表可以正常輸出

---

### Step 2：補強優化指標

在 `param_search.py` 和 `multi_segment_param_search.py` 的結果統計區塊，加入：

```python
# 新增指標計算
import numpy as np

def calc_sharpe(pnl_list, risk_free=0.0):
    arr = np.array(pnl_list)
    if arr.std() == 0 or len(arr) < 5:
        return 0.0
    return float((arr.mean() - risk_free) / arr.std() * np.sqrt(len(arr)))

def calc_max_drawdown(pnl_list):
    cum = np.cumsum(pnl_list)
    peak = np.maximum.accumulate(cum)
    dd = (peak - cum).max()
    return float(dd)

def calc_profit_factor(pnl_list):
    gains = sum(p for p in pnl_list if p > 0)
    losses = abs(sum(p for p in pnl_list if p < 0))
    return round(gains / losses, 3) if losses > 0 else float('inf')
```

結果 dict 新增欄位：`Sharpe`、`最大回撤`、`獲利因子`

**最佳參數排序改為**：Sharpe 降序（主），總損益降序（副）

---

### Step 3：加入分級統計

修改 param search 的進場紀錄，額外記錄 `entry_level`：

```python
# check_entry_signal 已回傳 info["level"]
trade_logs.append({
    "pnl": pnl,
    "level": entry.get("entry_level", "NA")
})
```

輸出結果增加 per-level 分解欄位：
- `A級_勝率`, `A級_單數`, `AB級_勝率`, `AB級_單數`, `B級_勝率`, `B級_單數`, `C級_勝率`, `C級_單數`

---

### Step 4：擴大搜尋空間

在 `multi_segment_param_search.py` 的參數 grid 加入：

```python
lookback_list = [2, 3, 5]               # 原本硬編 3
ab_threshold_list = [0.005, 0.01, 0.02] # 原本硬編 0.01（在 strategy.py 全域）

# 注意：ab_level_threshold 目前是 strategy.py 的全域變數
# 需改成 judge_signal_level() 的參數才能在搜尋中獨立控制
```

`SMCStrategy.__init__` 加 `ab_threshold` 參數，傳入 `judge_signal_level`（需同步修改 `strategy.py`）

---

### Step 5：Walk-Forward 結果自動寫回 config

Walk-forward 跑完後，自動輸出一個 `suggested_config_update.py`：

```python
# 範例輸出
STRATEGY_PARAMS = {
    "smc": {"lookback": 3, "tol_fvg": 0.003, "tp_r": 1.15},
    "smc_loose": {"lookback": 2, "tol_fvg": 0.002, "tp_r": 1.10},
}
# Walk-Forward Sharpe: smc=0.82, smc_loose=0.91
# 建議以此取代 config.py 中的 STRATEGY_PARAMS
```

同時加入「是否自動覆蓋 config.py」的 flag（預設 False，手動確認後改 True）：

```python
AUTO_APPLY = False   # 改 True 時直接覆寫 config.py
```

---

### Step 6：`backtest.py` 對齊實盤策略（選做）

**選項 A（建議）**：保留 `backtest.py` 使用 `strategy_periodic.py`，但在檔案頂端加上大字警語：
```
# 注意：此腳本使用 strategy_periodic.py，與實盤 STRATEGY_MAP 不同
# 參數優化請用 multi_segment_param_search.py
```

**選項 B**：把 `backtest.py` 改成也接受 `strategy_class` 參數，可傳入任意 class，
讓同一個腳本能跑 periodic 或 main 策略

---

## 執行順序

```
Step 1（crash fix）→ Step 2（指標）→ Step 3（分級）
→ 重新跑一次 historical_data 的搜尋，看新指標
→ Step 4（擴大搜尋空間）→ 再跑一輪
→ Step 5（auto-apply）
→ Step 6（選做，視需求）
→ 接實盤
```

---

## 關鍵風險

| 風險 | 說明 | 緩解 |
|------|------|------|
| `ab_level_threshold` 改成參數會影響 `strategy.py` 全域 | 要小心 `strategy_periodic.py` 也依賴它 | 先加 default=原值，保持向後相容 |
| 指標改為 Sharpe 主排序後，最佳參數可能與直覺差異大 | Sharpe 低單數時不穩定 | 加最小單數門檻（如 `單數 < 20` 時 Sharpe 視為無效）|
| Walk-forward 最佳參數在下一個區間未必好 | 這是回測本質限制 | 顯示 Walk-Forward 的「區間一致性分數」（各區間最佳參數的標準差）|
