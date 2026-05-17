import ccxt
import pandas as pd
import os
import sys
import time

# ==== 1. 設定幣種和 timeframe（與 download_ohlcv_multi.py 一致）====
symbols = ['BTC/USDT', 'ETH/USDT']
timeframes = ['15m', '30m', '1h', '4h']

# ==== 2. 建立存放資料夾 ====
os.makedirs("historical_data/oi", exist_ok=True)

force = '--force' in sys.argv

# ==== 3. 使用 Binance 期貨（支援公開 OI 歷史資料）====
exchange = ccxt.binanceusdm()

# ==== 4. 逐幣種與 timeframe 批次下載 ====
for symbol in symbols:
    for tf in timeframes:
        symbol_name = symbol.replace('/', '')
        fname = f"historical_data/oi/{symbol_name}_{tf}_oi.csv"

        if os.path.exists(fname) and not force:
            print(f"[SKIP] {fname} 已存在，略過（加 --force 可強制重新下載）")
            continue

        print(f"\n=== 正在下載 {symbol} {tf} OI ===")
        try:
            data = exchange.fetch_open_interest_history(symbol, tf, limit=300)
            if not data:
                print(f"[WARN] {symbol} {tf} OI 無資料")
                continue

            rows = []
            for d in data:
                ts = d['timestamp'] // 1000  # ms → 秒
                oi = d.get('openInterestAmount') or d.get('openInterest') or 0
                rows.append({'ts': ts, 'oi': oi})

            df = pd.DataFrame(rows)
            df.to_csv(fname, index=False)
            print(f"已存檔：{fname}，共 {len(df)} 筆")

        except Exception as e:
            print(f"[WARN] {symbol} {tf} OI 下載失敗：{e}")

        time.sleep(0.5)

print("\n全部 OI 資料下載完成！")
