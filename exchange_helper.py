# exchange_helper.py
from dotenv import load_dotenv
import os
import ccxt
import pandas as pd
import time
from logger import get_logger

_log = get_logger(__name__)

class ExchangeHelper:
    def __init__(self, use_sandbox=False):
        load_dotenv() 
        self.api_key = os.getenv("OKX_API_KEY")      # TODO: 填入你的OKX API KEY
        self.secret = os.getenv("OKX_API_SECRET")
        self.password = os.getenv("OKX_API_PASSWORD")
        self.use_sandbox = use_sandbox

        self.exchange = ccxt.okx({
            "apiKey": self.api_key,
            "secret": self.secret,
            "password": self.password,
            "enableRateLimit": True,
        })
        if use_sandbox:
            self.exchange.set_sandbox_mode(True)

        self._ohlcv_cache = {}
        self._oi_cache = {}
        self._oi_history_cache = {}

    def fetch_ohlcv(self, symbol, timeframe, limit=100):
        cache_key = f"{symbol}_{timeframe}_{limit}"
        now = int(time.time())
        # 簡易快取，每分鐘只抓一次
        if cache_key in self._ohlcv_cache:
            cache_time, cache_data = self._ohlcv_cache[cache_key]
            if now - cache_time < 60:
                return cache_data
        data = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        df = pd.DataFrame(data, columns=["ts", "open", "high", "low", "close", "vol"])
        self._ohlcv_cache[cache_key] = (now, df)
        return df

    def fetch_latest_bar(self, symbol, timeframe):
        df = self.fetch_ohlcv(symbol, timeframe, limit=2)
        return df.iloc[-1].to_dict()

    def open_position(self, symbol, side, size):
        # 實盤下單，請根據API需求調整
        _log.info(f"open_position: {symbol}, {side}, {size}")
        # demo用假order id
        return {"id": f"order_{int(time.time())}", "status": "open"}

    def close_position(self, symbol, order_id):
        _log.info(f"close_position: {symbol}, order_id={order_id}")
        # demo自動回傳已平倉
        return {"id": order_id, "status": "closed"}

    def fetch_balance(self):
        return self.exchange.fetch_balance()

    def fetch_open_interest(self, symbol):
        cache_key = symbol
        now = int(time.time())
        if cache_key in self._oi_cache:
            cache_time, cache_data = self._oi_cache[cache_key]
            if now - cache_time < 60:
                return cache_data
        try:
            raw = self.exchange.fetch_open_interest(symbol)
            result = {"oi": float(raw["openInterest"]), "timestamp": int(raw["timestamp"] or now)}
            self._oi_cache[cache_key] = (now, result)
            return result
        except Exception as e:
            _log.warning(f"fetch_open_interest({symbol}) 失敗: {e}")
            return None

    def fetch_oi_history(self, symbol, timeframe, limit=50):
        cache_key = f"{symbol}_{timeframe}_{limit}"
        now = int(time.time())
        if cache_key in self._oi_history_cache:
            cache_time, cache_data = self._oi_history_cache[cache_key]
            if now - cache_time < 60:
                return cache_data
        try:
            raw = self.exchange.fetch_open_interest_history(symbol, timeframe, limit=limit)
            df = pd.DataFrame(raw, columns=["ts", "oi"])
            self._oi_history_cache[cache_key] = (now, df)
            return df
        except Exception as e:
            _log.warning(f"fetch_oi_history({symbol}, {timeframe}) 失敗: {e}")
            return None

