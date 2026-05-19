import ccxt
import pandas as pd
import os
import sys
import time

# ==== 1. 設定幣種和 timeframe（與 download_ohlcv_multi.py 一致）====
symbols = ['BTC/USDT', 'ETH/USDT']
timeframes = ['15m', '30m', '1h', '4h']

# ==== 2. 停止往前抓的最早時間 ====
stop_ts_ms = 1672531200000  # 2023-01-01 00:00:00 UTC（毫秒）
max_limit = 500

# ==== 3. 建立存放資料夾 ====
os.makedirs("historical_data/oi", exist_ok=True)

force = '--force' in sys.argv

# ==== 4. 使用 Binance 期貨 ====
exchange = ccxt.binanceusdm()

# ==== 5. 逐幣種與 timeframe，從最新往前分頁下載 ====
for symbol in symbols:
    for tf in timeframes:
        symbol_name = symbol.replace('/', '')
        fname = f"historical_data/oi/{symbol_name}_{tf}_oi.csv"

        if os.path.exists(fname) and not force:
            print(f"[SKIP] {fname} 已存在，略過（加 --force 可強制重新下載）")
            continue

        print(f"\n=== 正在下載 {symbol} {tf} OI（從最新往前）===")
        all_rows = []
        end_time_ms = None  # 第一次不傳，抓最新

        try:
            while True:
                params = {}
                if end_time_ms is not None:
                    params["endTime"] = end_time_ms

                data = exchange.fetch_open_interest_history(symbol, tf, limit=max_limit, params=params)
                if not data:
                    break

                rows = []
                for d in data:
                    ts_ms = d['timestamp']
                    ts = ts_ms // 1000
                    oi = d.get('openInterestAmount') or d.get('openInterest') or 0
                    rows.append({'ts': ts, 'oi': oi})

                all_rows.extend(rows)
                oldest_ts_ms = data[0]['timestamp']
                print(f"  {symbol}-{tf}: 最舊抓到 {pd.to_datetime(oldest_ts_ms, unit='ms')}，累積 {len(all_rows)} 筆")

                # 已超過起始時間，停止
                if oldest_ts_ms <= stop_ts_ms:
                    break

                # 資料不足一頁，表示沒有更早的資料了
                if len(data) < max_limit:
                    break

                # 往前推：下次抓比最舊那筆更早的資料
                end_time_ms = oldest_ts_ms - 1
                time.sleep(0.5)

            if all_rows:
                df = pd.DataFrame(all_rows)
                df.drop_duplicates(subset='ts', inplace=True)
                df.sort_values('ts', inplace=True)
                # 只保留 2023-01-01 之後的資料
                df = df[df['ts'] >= stop_ts_ms // 1000]
                df.to_csv(fname, index=False)
                print(f"已存檔：{fname}，共 {len(df)} 筆，最早 {pd.to_datetime(df['ts'].min(), unit='s')}")
            else:
                print(f"[WARN] {symbol} {tf} OI 無資料")

        except Exception as e:
            print(f"[WARN] {symbol} {tf} OI 下載失敗：{e}")

        time.sleep(0.5)

print("\n全部 OI 歷史資料下載完成！")
