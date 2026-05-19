import ccxt
import pandas as pd
import os
import time

# ==== 1. 設定你要抓的幣種和 timeframe ====
symbols = ['BTC/USDT', 'ETH/USDT']      # 想抓更多幣只要加在這
timeframes = ['5m', '15m', '30m', '1h', '4h']              # 可以加 '4h', '1d' 等

# ==== 2. 下載歷史區間設定 ====
start_date = '2023-01-01T00:00:00Z'   # 從哪一天開始抓，可以自訂
max_limit = 1000                      # ccxt 單次最多 1000 根
exchange = ccxt.okx({"enableRateLimit": True})

# ==== 3. 建立存放資料的資料夾 ====
os.makedirs("historical_data", exist_ok=True)

# ==== 4. 逐幣種與 timeframe 批次下載 ====
for symbol in symbols:
    for tf in timeframes:
        print(f"\n=== 正在下載 {symbol} {tf} K線 ===")
        since = exchange.parse8601(start_date)
        all_data = []
        while True:
            # 抓資料
            data = exchange.fetch_ohlcv(symbol, timeframe=tf, since=since, limit=max_limit)
            if not data:
                break
            all_data += data
            # 印出目前下載進度
            print(f"{symbol}-{tf}: 已抓到 {pd.to_datetime(data[-1][0], unit='ms')}，累積 {len(all_data)} 筆")
            # 如果抓不到1000根，表示到頭了
            if len(data) < max_limit:
                break
            # 下次從這一輪最後一根的下一毫秒繼續抓
            since = data[-1][0] + 1
            # 如果怕限流，建議加點睡眠
            time.sleep(0.5)
        # 轉DataFrame、存檔
        if all_data:
            df = pd.DataFrame(all_data, columns=["ts", "open", "high", "low", "close", "vol"])
            df['ts'] = df['ts'] // 1000  # 轉成秒級 timestamp
            symbol_name = symbol.replace('/', '')
            fname = f"historical_data/{symbol_name}_{tf}.csv"
            df.to_csv(fname, index=False)
            print(f"已存檔：{fname}，共 {len(df)} 筆")
        else:
            print(f"[WARN] {symbol} {tf} 無資料")

print("\n全部幣種/週期下載完成！")
