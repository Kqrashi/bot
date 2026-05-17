# strategy.py
import pandas as pd
import pandas_ta as ta

# === OB/FVG ===
def detect_fvg(bars, tol=0.004, direction="long"):
    if len(bars) < 3:
        return False, None
    if direction == "long":
        h1 = bars['high'].iloc[-3]
        l3 = bars['low'].iloc[-1]
        gap = l3 - h1
        if gap > tol * bars['close'].iloc[-2]:
            return True, (h1, l3)
    else:  # short
        l1 = bars['low'].iloc[-3]
        h3 = bars['high'].iloc[-1]
        gap = l1 - h3
        if gap > tol * bars['close'].iloc[-2]:
            return True, (h3, l1)
    return False, None

def detect_ob(bars, direction="long"):
    if direction == "long":
        mask = bars['close'] < bars['open']
    else:
        mask = bars['close'] > bars['open']
    ob_cands = bars[mask]
    if len(ob_cands) == 0:
        return None
    ob = ob_cands.iloc[-1]
    return (ob['low'], ob['high'])

# 設定AB級的距離閾值（放到函數最前面 or 全域參數，方便調整）
AB_LEVEL_THRESHOLD = 0.01  # 或 0.003 / 0.01 依你想測試的寬鬆度

def judge_signal_level(bars, htf_bars, close, direction="long", tol=0.004):
    fvg_ok, fvg_range = detect_fvg(bars, tol=tol, direction=direction)
    ob_zone = detect_ob(bars, direction=direction)
    high = bars.iloc[-1]["high"]
    low = bars.iloc[-1]["low"]

    # === A級條件：完全同時觸及OB/FVG 或兩區本身有重疊 ===
    in_fvg = fvg_ok and (
        (fvg_range[0] <= close <= fvg_range[1]) or
        (fvg_range[0] <= high <= fvg_range[1]) or
        (fvg_range[0] <= low <= fvg_range[1])
    ) if fvg_ok else False
    in_ob = ob_zone and (
        (ob_zone[0] <= close <= ob_zone[1]) or
        (ob_zone[0] <= high <= ob_zone[1]) or
        (ob_zone[0] <= low <= ob_zone[1])
    ) if ob_zone else False

    overlap = False
    if fvg_ok and ob_zone:
        overlap = min(fvg_range[1], ob_zone[1]) > max(fvg_range[0], ob_zone[0])

    if (in_fvg and in_ob) or overlap:
        return "A"

    # === AB級條件（新版，允許接近OB/FVG的上下緣）===
    ab_trigger = False
    ab_dist = None

    if in_fvg and ob_zone:
        # 距離OB區間的最近端
        ob_dist = min(abs(close - ob_zone[0]), abs(close - ob_zone[1]))
        if ob_dist < AB_LEVEL_THRESHOLD * close:
            ab_trigger = True
            ab_dist = ob_dist

    if in_ob and fvg_ok and fvg_range:
        # 距離FVG區間的最近端
        fvg_dist = min(abs(close - fvg_range[0]), abs(close - fvg_range[1]))
        if fvg_dist < AB_LEVEL_THRESHOLD * close:
            ab_trigger = True
            ab_dist = fvg_dist if ab_dist is None else min(ab_dist, fvg_dist)

    if ab_trigger:
        return "AB"

    # === B級條件 ===
    if in_fvg or in_ob:
        return "B"

    return "C"



# === SMCStrategy 多空通用 ===
class SMCStrategy:
    def __init__(self, lookback=3, tol_fvg=0.004, tp_r=1.2):
        self.lookback = lookback
        self.tol_fvg = tol_fvg
        self.tp_r = tp_r

    def check_entry_signal(self, bar, bars, htf_bars, **kwargs):
        close = bars["close"].iloc[-1]
        rsi = ta.rsi(bars['close'], timeperiod=14)
        ma_fast = bars['close'].rolling(window=10).mean().iloc[-1]
        ma_slow = bars['close'].rolling(window=30).mean().iloc[-1]
        atr = ta.atr(bars['high'], bars['low'], bars['close'], timeperiod=14)

        # === 多單判斷 ===
        if (
            rsi.iloc[-1] < 35 and
            ma_fast > ma_slow and
            atr.iloc[-1] > 10
        ):
            level = judge_signal_level(bars, htf_bars, close, direction="long", tol=self.tol_fvg)
            if level:
                ob_zone = detect_ob(bars, direction="long")
                signal = True
                side = "long"
                if level == "A":
                    stop = ob_zone[0] * 0.998 if ob_zone else bars["low"].iloc[-1] * 0.98
                elif level == "AB":
                    stop = ob_zone[0] * 0.997 if ob_zone else bars["low"].iloc[-1] * 0.985
                elif level == "B":
                    stop = ob_zone[0] * 0.996 if ob_zone else bars["low"].iloc[-1] * 0.985
                else:
                    stop = bars["low"].iloc[-1] * 0.995
                tp = close * self.tp_r
                info = {"stop": stop, "tp": tp, "level": level}
                return signal, side, info

        # === 空單判斷 ===
        if (
            rsi.iloc[-1] > 65 and
            ma_fast < ma_slow and
            atr.iloc[-1] > 10
        ):
            level = judge_signal_level(bars, htf_bars, close, direction="short", tol=self.tol_fvg)
            if level:
                ob_zone = detect_ob(bars, direction="short")
                signal = True
                side = "short"
                if level == "A":
                    stop = ob_zone[1] * 1.002 if ob_zone else bars["high"].iloc[-1] * 1.02
                elif level == "AB":
                    stop = ob_zone[1] * 1.003 if ob_zone else bars["high"].iloc[-1] * 1.015
                elif level == "B":
                    stop = ob_zone[1] * 1.004 if ob_zone else bars["high"].iloc[-1] * 1.015
                else:
                    stop = bars["high"].iloc[-1] * 1.005
                tp = close * (2 - self.tp_r)
                info = {"stop": stop, "tp": tp, "level": level}
                return signal, side, info

        return False, "", {}

    def check_exit_signal(self, bar, bars, side, entry_price, stop, tp, **kwargs):
        if side == "long" and (bar["close"] <= stop or bar["close"] >= tp):
            return True
        if side == "short" and (bar["close"] >= stop or bar["close"] <= tp):
            return True
        return False

LEVEL_RANK = {"A": 3, "AB": 2, "B": 1, "C": 0}


# === 放寬條件版 SMCStrategyLoose ===
class SMCStrategyLoose(SMCStrategy):
    def check_entry_signal(self, bar, bars, htf_bars, **kwargs):
        close = bars["close"].iloc[-1]
        level_long = judge_signal_level(bars, htf_bars, close, direction="long", tol=self.tol_fvg)
        level_short = judge_signal_level(bars, htf_bars, close, direction="short", tol=self.tol_fvg)
        rank_long = LEVEL_RANK[level_long]
        rank_short = LEVEL_RANK[level_short]

        # 雙邊都是 C（無 confluence），或同分（方向矛盾），都跳過
        if rank_long == rank_short:
            return False, "", {}
        if rank_long == 0 and rank_short == 0:
            return False, "", {}

        if rank_long > rank_short:
            side = "long"
            level = level_long
            ob_zone = detect_ob(bars, direction="long")
            if level == "A":
                stop = ob_zone[0] * 0.998 if ob_zone else bars["low"].iloc[-1] * 0.98
            elif level == "AB":
                stop = ob_zone[0] * 0.997 if ob_zone else bars["low"].iloc[-1] * 0.985
            elif level == "B":
                stop = ob_zone[0] * 0.996 if ob_zone else bars["low"].iloc[-1] * 0.985
            else:
                stop = bars["low"].iloc[-1] * 0.995
            tp = close * self.tp_r
        else:
            side = "short"
            level = level_short
            ob_zone = detect_ob(bars, direction="short")
            if level == "A":
                stop = ob_zone[1] * 1.002 if ob_zone else bars["high"].iloc[-1] * 1.02
            elif level == "AB":
                stop = ob_zone[1] * 1.003 if ob_zone else bars["high"].iloc[-1] * 1.015
            elif level == "B":
                stop = ob_zone[1] * 1.004 if ob_zone else bars["high"].iloc[-1] * 1.015
            else:
                stop = bars["high"].iloc[-1] * 1.005
            tp = close * (2 - self.tp_r)

        info = {"stop": stop, "tp": tp, "level": level}
        return True, side, info

# === SMC + 趨勢過濾（僅保留原有多單邏輯） ===
class SMCWithTrendStrategy:
    def __init__(self, lookback=3, tol_fvg=0.004, tp_r=1.2, trend_ma_fast=20, trend_ma_slow=60, trend_filter=True):
        self.lookback = lookback
        self.tol_fvg = tol_fvg
        self.tp_r = tp_r
        self.trend_ma_fast = trend_ma_fast
        self.trend_ma_slow = trend_ma_slow
        self.trend_filter = trend_filter

    def _ma(self, series, window):
        return series.rolling(window=window).mean()

    def check_entry_signal(self, bar, bars, htf_bars, **kwargs):
        close = bars["close"].iloc[-1]
        bars = bars.copy()
        bars["ma_fast"] = self._ma(bars["close"], self.trend_ma_fast)
        bars["ma_slow"] = self._ma(bars["close"], self.trend_ma_slow)
        trend = bars["ma_fast"].iloc[-1] > bars["ma_slow"].iloc[-1]
        prev_high = htf_bars["high"].max()
        signal = False
        side = ""
        info = {}
        if self.trend_filter and trend and close > prev_high:
            signal = True
            side = "long"
            info["stop"] = bars["low"].iloc[-1] * 0.98
            info["tp"] = close * self.tp_r
        return signal, side, info

    def check_exit_signal(self, bar, bars, side, entry_price, stop, tp, **kwargs):
        if side == "long" and (bar["close"] <= stop or bar["close"] >= tp):
            return True
        if side == "short" and (bar["close"] >= stop or bar["close"] <= tp):
            return True
        return False

# 策略註冊表
STRATEGY_MAP = {
    "smc": SMCStrategy(),
    "smc_loose": SMCStrategyLoose(),
    "smc_trend": SMCWithTrendStrategy()
}
