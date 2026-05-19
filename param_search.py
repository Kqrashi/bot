import os
import pandas as pd
from datetime import datetime
from strategy import SMCStrategy, SMCStrategyLoose, judge_signal_level
from constants import ALLOWED_LEVELS_MAP
import glob

FEE_RATE = 0.001  # 進出各 0.05%，合計 0.1%

os.makedirs("search_results", exist_ok=True)

strategy_classes = {
    "smc": SMCStrategy,
    "smc_loose": SMCStrategyLoose
}

results = []

# 搜尋 historical_data 資料夾下所有 _5m.csv 檔案
csv_files = glob.glob("historical_data/*.csv")

for csv_path in csv_files:
    filename = os.path.basename(csv_path).replace('.csv', '')  # 取檔名當幣種名稱
    parts = filename.split('_')
    symbol = parts[0]         # BTCUSDT 或 ETHUSDT
    timeframe = parts[1]      # 1h, 4h, 15m, 30m, ...
    allowed_levels = ALLOWED_LEVELS_MAP.get(timeframe, ["A", "AB", "B", "C"])
    print(f"\n====== 目前處理 {symbol} {timeframe}（允許級別：{allowed_levels}）======")
    df = pd.read_csv(csv_path)
    for strategy_name, strategy_class in strategy_classes.items():
        for tp_r in [1.05, 1.1, 1.15, 1.2]:
            for tol_fvg in [0.002, 0.003, 0.004, 0.005]:
                strategy = strategy_class(tp_r=tp_r, tol_fvg=tol_fvg)
                trade_logs = []
                entry = None
                for i in range(100, len(df)):
                    bars = df.iloc[i-100:i]
                    htf_bars = df.iloc[max(0, i-500):i]
                    bar = bars.iloc[-1]
                    sig, side, info = strategy.check_entry_signal(bar, bars, htf_bars)
                    # 套用 ALLOWED_LEVELS_MAP 過濾
                    if sig and info.get("level") not in allowed_levels:
                        sig = False
                    if sig and entry is None:
                        entry = {
                            "side": side,
                            "entry_price": bar["close"],
                            "stop": info.get("stop", bar["low"]*0.98),
                            "tp": info.get("tp", bar["close"]*tp_r),
                            "entry_time": bar["ts"],
                            "size": 1
                        }
                    elif entry is not None:
                        should_exit = strategy.check_exit_signal(
                            bar, bars, entry["side"], entry["entry_price"], entry["stop"], entry["tp"]
                        )
                        if should_exit:
                            pnl = (bar["close"] - entry["entry_price"]) / entry["entry_price"] if entry["side"] == "long" \
                                else (entry["entry_price"] - bar["close"]) / entry["entry_price"]
                            trade_logs.append(pnl - FEE_RATE)
                            entry = None
                # 統計結果
                total_pnl = sum(trade_logs)
                win_rate = sum([1 for p in trade_logs if p > 0]) / len(trade_logs) if trade_logs else 0
                print(f"已完成：symbol={symbol}, strategy={strategy_name}, tp_r={tp_r}, tol_fvg={tol_fvg}, trade數={len(trade_logs)}")
                results.append({
                    "symbol": symbol,  # <== 新增欄位標記幣種
                    "timeframe": timeframe,   # <--- 新增時框欄位
                    "strategy": strategy_name,
                    "tp_r": tp_r,
                    "tol_fvg": tol_fvg,
                    "總損益": total_pnl,
                    "勝率": win_rate,
                    "單數": len(trade_logs)
                })

# 匯出總績效表
res_df = pd.DataFrame(results)
res_df = res_df.sort_values(["symbol", "strategy", "總損益"], ascending=[True, True, False])
print(res_df)

now_str = datetime.now().strftime('%Y%m%d_%H%M%S')
res_df.to_csv(f"search_results/param_search_results_{now_str}.csv", index=False, encoding="utf-8-sig")
