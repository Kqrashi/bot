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

    def open_position(self, symbol, side, size_contracts, max_retry=3):
        _log.info(f"open_position: {symbol} {side} {size_contracts} contracts")
        for attempt in range(max_retry):
            try:
                import ccxt
                order = self.exchange.create_order(
                    symbol, "market", side, size_contracts,
                    params={"tdMode": "cross", "posSide": "net"}
                )
                return {"id": order["id"], "status": order.get("status", "open")}
            except ccxt.NetworkError as e:
                _log.warning(f"open_position 網路錯誤(第{attempt+1}次): {e}")
                time.sleep(2 ** attempt)
            except Exception as e:
                _log.error(f"open_position 失敗: {e}")
                from notifier import notify_error
                notify_error("open_position", e)
                return None
        _log.error("open_position 重試耗盡")
        return None

    def close_position(self, symbol, side, size_contracts, max_retry=3):
        close_side = "sell" if side == "long" else "buy"
        _log.info(f"close_position: {symbol} {close_side} {size_contracts} contracts")
        for attempt in range(max_retry):
            try:
                import ccxt
                order = self.exchange.create_order(
                    symbol, "market", close_side, size_contracts,
                    params={"tdMode": "cross", "posSide": "net", "reduceOnly": True}
                )
                return {"id": order["id"], "status": order.get("status", "closed")}
            except ccxt.NetworkError as e:
                _log.warning(f"close_position 網路錯誤(第{attempt+1}次): {e}")
                time.sleep(2 ** attempt)
            except Exception as e:
                _log.error(f"close_position 失敗: {e}")
                return None
        _log.error("close_position 重試耗盡")
        return None

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

