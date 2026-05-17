# backtest.py
import pandas as pd
import os
import glob
from config import STRATEGY_PERIODIC_MAP, STRATEGY_PERIODIC_PARAMS
from constants import ALLOWED_LEVELS_MAP

def run_backtest(data_dir="historical_data", out_dir="backtest_results"):
    os.makedirs(out_dir, exist_ok=True)
    csv_files = glob.glob(os.path.join(data_dir, "*.csv"))
    # 你可改這一行，決定只做哪些級別
    ALLOWED_ENTRY_LEVELS = ["A", "B", "AB"]  # 只做A級、AB級（可改成["A", "B", "C"]等）
    
    for csv_path in csv_files:
        
        filename = os.path.basename(csv_path).replace('.csv', '')
        parts = filename.split('_')
        if len(parts) < 2:
            print(f"[WARN] 檔名格式不正確: {csv_path}")
            continue
        symbol = parts[0]
        timeframe = parts[1]
        ALLOWED_ENTRY_LEVELS = ALLOWED_LEVELS_MAP.get(timeframe, ["A", "AB", "B", "C"])
        df = pd.read_csv(csv_path)
        
        # 根據週期自動挑策略與參數
        StrategyClass = STRATEGY_PERIODIC_MAP.get(timeframe)
        params = STRATEGY_PERIODIC_PARAMS.get(timeframe, {})
        if StrategyClass is None:
            print(f"[WARN] 不支援此週期 {timeframe}，略過！")
            continue

        strategy = StrategyClass(**params)
        entry = None
        trade_logs = []

        # 嘗試載入對應 OI 資料
        oi_path = f"historical_data/oi/{symbol}_{timeframe}_oi.csv"
        if os.path.exists(oi_path):
            oi_data = pd.read_csv(oi_path)
        else:
            oi_data = None

        for i in range(100, len(df)):
            bars = df.iloc[i-100:i]
            htf_bars = df.iloc[max(0, i-500):i]
            bar = bars.iloc[-1]

            # 切出當前 bar 時間點之前最近 50 筆 OI
            if oi_data is not None:
                oi_df = oi_data[oi_data["ts"] <= bar["ts"]].tail(50)
                oi_df = oi_df if len(oi_df) >= 6 else None
            else:
                oi_df = None

            sig, side, info = strategy.check_entry_signal(
                bar, bars, htf_bars, oi_df=oi_df, bars_for_cvd=bars, **params
            )
            entry_level = info.get("level", "NA")
            # <<<<<< 只做允許的級別 >>>>>>
            if sig and entry is None and entry_level in ALLOWED_ENTRY_LEVELS:
                entry = {
                    "side": side,
                    "entry_price": bar["close"],
                    "stop": info.get("stop", bar["low"]*0.98 if side=="long" else bar["high"]*1.02),
                    "tp": info.get("tp", bar["close"]*1.2 if side=="long" else bar["close"]*0.8),
                    "entry_time": bar["ts"],
                    "size": 1,
                    "entry_level": entry_level,
                    "oi_filtered": oi_df is not None,
                }
            elif entry is not None:
                should_exit = strategy.check_exit_signal(
                    bar, bars, entry["side"], entry["entry_price"], entry["stop"], entry["tp"]
                )
                if should_exit:
                    close_price = bar["close"]
                    pnl = (close_price - entry["entry_price"]) if entry["side"] == "long" \
                        else (entry["entry_price"] - close_price)
                    trade_logs.append({
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "strategy": StrategyClass.__name__,
                        "side": entry["side"],
                        "entry_time": entry["entry_time"],
                        "entry_price": entry["entry_price"],
                        "stop": entry["stop"],
                        "tp": entry["tp"],
                        "size": entry["size"],
                        "exit_time": bar["ts"],
                        "exit_price": close_price,
                        "pnl": pnl,
                        "reason": "TP/SL/BMS/CHOCH",
                        "entry_level": entry["entry_level"],
                        "oi_filtered": entry.get("oi_filtered", False),
                    })
                    entry = None
        # 匯出結果
        if trade_logs:
            df_log = pd.DataFrame(trade_logs)
            out_file = os.path.join(out_dir, f"backtest_{symbol}_{timeframe}_{StrategyClass.__name__}.csv")
            df_log.to_csv(out_file, index=False)
            print(f"[INFO] {out_file} 匯出 {len(trade_logs)} 筆回測交易")

if __name__ == "__main__":
    run_backtest()
