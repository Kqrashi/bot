# backtest.py
import pandas as pd
import os
import glob
from config import STRATEGY_PERIODIC_MAP, STRATEGY_PERIODIC_PARAMS
from constants import ALLOWED_LEVELS_MAP
from metrics import compute_metrics

FEE_RATE = 0.001  # 進出各 0.05%，合計 0.1%

def run_backtest(data_dir="historical_data", out_dir="backtest_results"):
    os.makedirs(out_dir, exist_ok=True)
    csv_files = glob.glob(os.path.join(data_dir, "*.csv"))

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

        StrategyClass = STRATEGY_PERIODIC_MAP.get(timeframe)
        params = STRATEGY_PERIODIC_PARAMS.get(timeframe, {})
        if StrategyClass is None:
            print(f"[WARN] 不支援此週期 {timeframe}，略過！")
            continue

        strategy = StrategyClass(**params)
        entry = None
        pending_signal = None
        trade_logs = []

        # 嘗試載入對應 OI 資料
        oi_path = os.path.join("historical_data", "oi", f"{symbol}_{timeframe}_oi.csv")
        if os.path.exists(oi_path):
            oi_data = pd.read_csv(oi_path)
        else:
            oi_data = None

        for i in range(100, len(df) - 1):
            bars = df.iloc[i-100:i]
            htf_bars = df.iloc[max(0, i-500):i]
            bar = bars.iloc[-1]
            next_open = df.iloc[i]["open"]

            # 切出當前 bar 時間點之前最近 50 筆 OI
            if oi_data is not None:
                oi_df = oi_data[oi_data["ts"] <= int(bar["ts"])].tail(50)
                oi_df = oi_df if len(oi_df) >= 6 else None
            else:
                oi_df = None

            # pending 訊號 → 次 bar open 成交
            if pending_signal is not None and entry is None:
                entry = {
                    "side": pending_signal["side"],
                    "entry_price": next_open,
                    "stop": pending_signal["stop"],
                    "tp": pending_signal["tp"],
                    "entry_time": pending_signal["entry_time"],
                    "size": 1,
                    "entry_level": pending_signal["entry_level"],
                    "oi_filtered": pending_signal["oi_filtered"],
                }
                pending_signal = None

            # 出場：止損/止盈穿越用確切價格出場
            if entry is not None:
                exit_price = None
                if entry["side"] == "long":
                    if bar["low"] <= entry["stop"]:
                        exit_price = entry["stop"]
                    elif bar["high"] >= entry["tp"]:
                        exit_price = entry["tp"]
                else:
                    if bar["high"] >= entry["stop"]:
                        exit_price = entry["stop"]
                    elif bar["low"] <= entry["tp"]:
                        exit_price = entry["tp"]

                if exit_price is None:
                    should_exit = strategy.check_exit_signal(
                        bar, bars, entry["side"], entry["entry_price"], entry["stop"], entry["tp"]
                    )
                    if should_exit:
                        exit_price = bar["close"]

                if exit_price is not None:
                    if entry["side"] == "long":
                        pnl = (exit_price - entry["entry_price"]) / entry["entry_price"]
                    else:
                        pnl = (entry["entry_price"] - exit_price) / entry["entry_price"]
                    pnl_net = pnl - FEE_RATE
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
                        "exit_price": exit_price,
                        "pnl_pct": round(pnl, 6),
                        "pnl_net_pct": round(pnl_net, 6),
                        "fee": FEE_RATE,
                        "reason": "TP/SL/BMS/CHOCH",
                        "entry_level": entry["entry_level"],
                        "oi_filtered": entry.get("oi_filtered", False),
                    })
                    entry = None

            # 進場訊號存入 pending（下一根執行）
            if entry is None and pending_signal is None:
                sig, side, info = strategy.check_entry_signal(
                    bar, bars, htf_bars, oi_df=oi_df, bars_for_cvd=bars, **params
                )
                entry_level = info.get("level", "NA")
                if sig and entry_level in ALLOWED_ENTRY_LEVELS:
                    tp_default = bar["close"] * params.get("tp_r", 1.2) if side == "long" else bar["close"] * (2 - params.get("tp_r", 1.2))
                    pending_signal = {
                        "side": side,
                        "stop": info.get("stop", bar["low"] * 0.98 if side == "long" else bar["high"] * 1.02),
                        "tp": info.get("tp", tp_default),
                        "entry_time": bar["ts"],
                        "entry_level": entry_level,
                        "oi_filtered": oi_df is not None,
                    }

        # 匯出結果
        if trade_logs:
            df_log = pd.DataFrame(trade_logs)
            oi_true = df_log["oi_filtered"].sum()
            oi_false = len(df_log) - oi_true
            pnl_list = df_log["pnl_net_pct"].tolist()
            sharpe, max_dd, pf = compute_metrics(pnl_list)
            print(f"[OI] {symbol} {timeframe}: oi_filtered True={oi_true}, False={oi_false} (共 {len(df_log)} 筆)")
            print(f"[績效] Sharpe={sharpe:.3f}, MaxDD={max_dd:.3%}, PF={pf:.3f}")
            out_file = os.path.join(out_dir, f"backtest_{symbol}_{timeframe}_{StrategyClass.__name__}.csv")
            df_log.to_csv(out_file, index=False)
            print(f"[INFO] {out_file} 匯出 {len(trade_logs)} 筆回測交易")

if __name__ == "__main__":
    run_backtest()
