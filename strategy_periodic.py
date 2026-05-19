# strategy_periodic.py
from strategy import SMCStrategy, SMCStrategyLoose, judge_signal_level, detect_ob
from constants import ALLOWED_LEVELS_MAP

class BaseSMCStrategy:
    TIMEFRAME = "5m"
    STRATEGY_CLASS = SMCStrategyLoose
    TP_R_DEFAULT = 1.01
    TOL_FVG_DEFAULT = 0.002

    def __init__(self, **kwargs):
        self.tp_r = kwargs.get("tp_r", self.TP_R_DEFAULT)
        self.tol_fvg = kwargs.get("tol_fvg", self.TOL_FVG_DEFAULT)
        self.strategy = self.STRATEGY_CLASS(tp_r=self.tp_r, tol_fvg=self.tol_fvg)
        self.allowed_levels = ALLOWED_LEVELS_MAP[self.TIMEFRAME]

    def check_entry_signal(self, bar, bars, htf_bars, **kwargs):
        close = bars["close"].iloc[-1]
        level_long = judge_signal_level(bars, htf_bars, close, direction="long", tol=self.tol_fvg)
        level_short = judge_signal_level(bars, htf_bars, close, direction="short", tol=self.tol_fvg)
        if level_long not in self.allowed_levels and level_short not in self.allowed_levels:
            return False, "", {}
        return self.strategy.check_entry_signal(bar, bars, htf_bars, **kwargs)

    def check_exit_signal(self, *args, **kwargs):
        return self.strategy.check_exit_signal(*args, **kwargs)

# ==== 各 timeframe 子類別 ====

class FiveMinStrategy(BaseSMCStrategy):
    TIMEFRAME = "5m"
    STRATEGY_CLASS = SMCStrategyLoose
    TP_R_DEFAULT = 1.01
    TOL_FVG_DEFAULT = 0.0015

class FifteenMinStrategy(BaseSMCStrategy):
    TIMEFRAME = "15m"
    STRATEGY_CLASS = SMCStrategyLoose
    TP_R_DEFAULT = 1.10
    TOL_FVG_DEFAULT = 0.0015

class ThirtyMinStrategy(BaseSMCStrategy):
    TIMEFRAME = "30m"
    STRATEGY_CLASS = SMCStrategyLoose
    TP_R_DEFAULT = 1.13
    TOL_FVG_DEFAULT = 0.002

class OneHourStrategy(BaseSMCStrategy):
    TIMEFRAME = "1h"
    STRATEGY_CLASS = SMCStrategy
    TP_R_DEFAULT = 1.18
    TOL_FVG_DEFAULT = 0.0025

class FourHourStrategy(BaseSMCStrategy):
    TIMEFRAME = "4h"
    STRATEGY_CLASS = SMCStrategy
    TP_R_DEFAULT = 1.22
    TOL_FVG_DEFAULT = 0.0025

    # 4h 額外要求突破確認，level 過濾已由 BaseSMCStrategy 處理
    def check_entry_signal(self, bar, bars, htf_bars, **kwargs):
        sig, side, info = super().check_entry_signal(bar, bars, htf_bars, **kwargs)
        if not sig:
            return False, "", {}
        close = bars["close"].iloc[-1]
        if side == "long" and close > bars["high"].iloc[-5:-1].max():
            ob_zone = detect_ob(bars, direction="long")
            info["stop"] = ob_zone[0] * 0.99 if ob_zone else bars["low"].iloc[-1] * 0.98
            info["tp"] = close * self.tp_r
            return True, "long", info
        if side == "short" and close < bars["low"].iloc[-5:-1].min():
            ob_zone = detect_ob(bars, direction="short")
            info["stop"] = ob_zone[1] * 1.01 if ob_zone else bars["high"].iloc[-1] * 1.02
            info["tp"] = close * (2 - self.tp_r)
            return True, "short", info
        return False, "", {}

# 你要加日線/週線策略，只要照這個 pattern 新增 class 即可
