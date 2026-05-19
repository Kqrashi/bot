# Plan: 自愈模組（Self-Healing Agent）

**範圍**：程式碼層級 bug 自動修復，config/參數優化是獨立功能，之後再加。
**確認機制**：AI 生成 patch + 報告 → 用戶確認 → 才套用。

---

## 設計原則

1. **人永遠有最後決定權**：所有 patch 都需要你輸入指令確認，不會自動生效
2. **透明度優先**：報告必須解釋「為什麼出錯」和「改了什麼」，不能只說「已修復」
3. **保守邊界**：以下檔案 AI 不能碰：`exchange_helper.py`（下單）、`risk.py`（風控）、`config.py`（主設定）
4. **可回滾**：套用前自動備份原始檔案，確認後如果還是有問題可以一鍵還原

---

## 架構

```
Exception 發生
    ↓
main.py 的 except 區塊捕獲
    ↓
healer.py 分析 (呼叫 Claude API)
    ↓
生成 pending_fixes/{timestamp}.json (含 patch + 報告)
    ↓
發送報告（目前：寫到 healer_reports/ 資料夾 + console 印出）
    ↓
交易暫停（只暫停出錯的 symbol/strategy）
    ↓
等待用戶確認：python healer.py confirm <ID>
    ↓
套用 patch → py_compile 語法檢查 → 備份原始檔
    ↓
輸出套用確認報告 → 恢復交易
```

---

## 新增檔案

### `healer.py`

主模組，對外提供兩個介面：

**1. `analyze(error, context)` → 給 main.py 呼叫**

```python
def analyze(error: Exception, context: dict) -> str:
    """
    error: 捕獲的例外
    context: {
        "symbol": "BTC/USDT",
        "strategy": "smc",
        "bar": {...},          # 出事當下的 K 線
        "traceback": "...",    # 完整 traceback 字串
        "file": "strategy.py", # 出錯的檔案
        "line": 112            # 出錯的行號
    }
    回傳：fix_id（用來確認用）
    """
```

內部流程：
1. 讀取出錯的原始檔案內容
2. 呼叫 Claude API（`claude-haiku-4-5`，夠便宜、夠快）
3. Prompt 結構：
   ```
   你是一個 Python 交易機器人的 debug 助手。
   以下是出錯的程式碼、traceback、和當下的市場資料。
   請分析根本原因，並提供 unified diff 格式的最小修改。
   不要改超出必要範圍。
   ```
4. 解析回傳的 diff
5. 儲存到 `pending_fixes/{fix_id}.json`
6. 印出報告摘要

**2. CLI 確認介面**

```bash
python healer.py list              # 看所有待確認的 fix
python healer.py show <fix_id>     # 看完整報告和 diff
python healer.py confirm <fix_id>  # 套用
python healer.py reject <fix_id>   # 拒絕並丟棄
python healer.py rollback <fix_id> # 已套用但想還原
```

---

## 報告格式（`healer_reports/{fix_id}.txt`）

```
╔══════════════════════════════════════╗
║      自愈報告 #20260518-001          ║
╚══════════════════════════════════════╝

發生時間：2026-05-18 14:23:11
影響範圍：BTC/USDT × 策略 smc（已暫停）
出錯位置：strategy.py，第 112 行

【錯誤訊息】
KeyError: 'rsi'
  File "strategy.py", line 112, in check_entry_signal
    rsi.iloc[-1] < 35

【AI 分析：為什麼出錯】
pandas_ta.rsi() 在 K 線資料不足 14 根時回傳空 Series，
此時 .iloc[-1] 會拋出 IndexError 而非 KeyError。
追蹤顯示出事當下 bars 只有 8 根（可能是新幣種第一次執行）。

【建議修改】
--- a/strategy.py
+++ b/strategy.py
@@ -108,6 +108,9 @@ class SMCStrategy:
     def check_entry_signal(self, bar, bars, htf_bars, ...):
         close = bars["close"].iloc[-1]
         rsi = ta.rsi(bars['close'], timeperiod=14)
+        if rsi is None or len(rsi.dropna()) < 2:
+            return False, "", {}
         ma_fast = bars['close'].rolling(window=10).mean().iloc[-1]

【修改說明】
在 RSI 計算後加入資料不足的提前返回，避免後續 .iloc[-1] 操作
在 K 線不足 14 根時崩潰。不影響正常情況下的邏輯。

【信心程度】92%
【影響其他策略】否（SMCStrategyLoose 繼承此方法，同樣受益）

【操作指令】
確認套用：python healer.py confirm 20260518-001
拒絕放棄：python healer.py reject 20260518-001
```

---

## 修改現有檔案

### `main.py`

在主迴圈的 `except Exception as e` 加入觸發邏輯：

```python
from healer import Healer

healer = Healer()  # 在 main() 開頭初始化

# ... 主迴圈 ...

except Exception as e:
    import traceback
    tb = traceback.format_exc()
    # 取得出錯位置
    tb_obj = sys.exc_info()[2]
    frame = traceback.extract_tb(tb_obj)[-1]

    context = {
        "symbol": symbol if 'symbol' in dir() else "unknown",
        "strategy": strategy_name if 'strategy_name' in dir() else "unknown",
        "traceback": tb,
        "file": frame.filename,
        "line": frame.lineno,
    }

    fix_id = healer.analyze(e, context)
    if fix_id:
        logger.error(f"[HEALER] 已生成修復建議，fix_id={fix_id}")
        logger.error(f"[HEALER] 查看報告：python healer.py show {fix_id}")
        logger.error(f"[HEALER] 確認套用：python healer.py confirm {fix_id}")
    else:
        logger.error(f"[HEALER] 無法生成修復建議，請手動檢查")

    time.sleep(60)
    continue
```

### `requirements.txt`

新增：
```
anthropic>=0.25.0
```

### `.env`

新增：
```
ANTHROPIC_API_KEY=your_key_here
```

---

## 安全護欄

| 規則 | 說明 |
|------|------|
| 禁止修改清單 | `exchange_helper.py`, `risk.py`, `config.py`, `healer.py` 本身 |
| 單日上限 | 最多自動分析 5 次（避免迴圈崩潰導致 API 費用爆炸） |
| Patch 範圍限制 | 只接受修改同一個函數內的程式碼，不接受新增 import 或跨函數修改 |
| 備份機制 | 套用前自動複製原始檔到 `healer_backups/{fix_id}_original_{filename}` |
| 語法驗證 | 套用後立刻跑 `py_compile`，失敗則自動回滾並通知 |

---

## 預期的用戶體驗

**平時**：機器人跑得好，什麼都不發生。

**出 bug 時**：
1. Console 出現：`[HEALER] 已生成修復建議，fix_id=20260518-001`
2. 你去看報告：`python healer.py show 20260518-001`
3. 覺得分析合理：`python healer.py confirm 20260518-001`
4. 套用成功，交易恢復，同時生成一份套用確認報告

**你不在的時候**：交易暫停，待你回來確認，不會自動亂改。

---

## 不包含的功能（之後再做）

- LINE / Email 通知（需要另外接 API）
- config / 參數的 AI 優化（規劃中的另一個獨立功能）
- Web 介面確認（CLI 夠用）

---

## 執行順序（相對於優化 Pipeline 計畫）

```
先跑：strategy-optimization-pipeline.md（Step 1~3）
然後：加入 self-healing-agent（不依賴前者）
最後：接實盤
```

這兩個計畫互相獨立，可以平行推進，也可以先做完優化再做自愈。
