# main.py
import os
import time
import pandas as pd
from datetime import datetime

from config import SYMBOLS, TIMEFRAME, STRATEGY_PARAMS, RISK_PARAMS, TRADE_LOG_DIR, BACKUP_DIR, START_EQUITY
from strategy import STRATEGY_MAP
from exchange_helper import ExchangeHelper
from risk import RiskEngine

def safe_append_to_csv(trade_record, csv_path, backup_path=None, max_retry=3):
    for attempt in range(max_retry):
        try:
            df = pd.DataFrame([trade_record])
            file_exists = os.path.isfile(csv_path)
            df.to_csv(csv_path, mode="a", header=not file_exists, index=False)
            if backup_path:
                file_exists_bak = os.path.isfile(backup_path)
                df.to_csv(backup_path, mode="a", header=not file_exists_bak, index=False)
            return True
        except Exception as e:
            print(f"[WARN] 寫入csv失敗: {e}")
            time.sleep(2)
    print(f"[FATAL] 多次嘗試寫檔失敗，資料暫存buffer等待下次寫入！")
    return False

def main():
    exchange = ExchangeHelper()
    risk = RiskEngine(equity=START_EQUITY, risk_pct=RISK_PARAMS.get("risk_pct", 0.01))
    open_trades = {}        # {(symbol, strategy): entry_info}
    trade_records_buffer = []

    while True:
        print("進入主迴圈...")
        try:
            today = datetime.now()
            month_folder = today.strftime("%Y-%m")
            today_str = today.strftime("%Y-%m-%d")
            base_dir = TRADE_LOG_DIR
            save_dir = os.path.join(base_dir, month_folder)
            os.makedirs(save_dir, exist_ok=True)
            os.makedirs(BACKUP_DIR, exist_ok=True)
            csv_path = os.path.join(save_dir, f"trade_log_{today_str}.csv")
            backup_path = os.path.join(BACKUP_DIR, f"trade_log_backup_{today_str}.csv")

            # 每小時更新一次策略權重
            if int(time.time()) % 3600 < 20:
                risk.update_strategy_weights(csv_path, window=50)

            for symbol in SYMBOLS:
                print(f"正在處理幣種: {symbol}")                    ##測試加的
                bar = exchange.fetch_latest_bar(symbol, TIMEFRAME)
                print(f"{symbol} 最新K線 bar: {bar}")               ##測試加的           
                bars = exchange.fetch_ohlcv(symbol, TIMEFRAME, limit=100)
                htf_bars = exchange.fetch_ohlcv(symbol, "1h", limit=100)

                for strategy_name, strategy in STRATEGY_MAP.items():
                    print(f"策略: {strategy_name} 準備檢查訊號")    ##測試加的
                    key = (symbol, strategy_name)
                    entry = open_trades.get(key, None)

                    params = STRATEGY_PARAMS.get(strategy_name, {})
                    sig, side, info = strategy.check_entry_signal(bar, bars, htf_bars, **params)

                    if sig and entry is None:
                        stop_price = info.get("stop", bar["low"] * 0.98 if side == "long" else bar["high"] * 1.02)
                        tp_price = info.get("tp", None)
                        size = risk.on_new_trade(info, strategy_name=strategy_name)
                        if size:
                            order = exchange.open_position(symbol, side, size)
                            open_trades[key] = {
                                "side": side,
                                "entry_price": bar['close'],
                                "stop": stop_price,
                                "tp": tp_price,
                                "entry_time": bar['ts'],
                                "order_id": order['id'],
                                "size": size
                            }
                            print(f"[INFO] Open {symbol} [{strategy_name}]: {side}, size: {size}, entry: {bar['close']}")

                    if entry is not None:
                        should_exit = strategy.check_exit_signal(
                            bar, bars,
                            entry.get("side"), entry.get("entry_price"),
                            entry.get("stop"), entry.get("tp")
                        )
                        if should_exit:
                            close_time = bar['ts']
                            close_price = bar['close']
                            pnl = (close_price - entry["entry_price"]) * entry["size"] if entry["side"] == "long" \
                                else (entry["entry_price"] - close_price) * entry["size"]
                            risk.equity += pnl
                            print(f"[INFO] equity 更新為 {risk.equity:.2f}（本筆 pnl={pnl:.2f}）")
                            trade_record = {
                                "symbol": symbol,
                                "strategy": strategy_name,
                                "side": entry["side"],
                                "entry_time": entry["entry_time"],
                                "entry_price": entry["entry_price"],
                                "stop": entry["stop"],
                                "tp": entry["tp"],
                                "size": entry["size"],
                                "exit_time": close_time,
                                "exit_price": close_price,
                                "pnl": pnl,
                                "order_id": entry["order_id"],
                                "reason": "TP/SL/BMS/CHOCH"
                            }
                            ok = safe_append_to_csv(trade_record, csv_path, backup_path)
                            if not ok:
                                trade_records_buffer.append(trade_record)
                            else:
                                if trade_records_buffer:
                                    print(f"[INFO] 補寫 {len(trade_records_buffer)} 筆buffer資料")
                                    for rec in trade_records_buffer:
                                        safe_append_to_csv(rec, csv_path, backup_path)
                                    trade_records_buffer.clear()
                            print(f"[INFO] Closed {symbol} [{strategy_name}] position, logged to {csv_path}")
                            del open_trades[key]

        except Exception as e:
            print("[FATAL] 主流程異常:", e)
            time.sleep(60)
            continue

        time.sleep(15)

if __name__ == "__main__":
    main()
