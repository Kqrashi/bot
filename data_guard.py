# data_guard.py — bar 品質檢測，防止跳空/缺量進場
from config import MAX_PRICE_JUMP_PCT


def check_bar_quality(bar: dict, prev_bar) -> tuple:
    if prev_bar is None:
        return True, ""
    try:
        change = abs(bar["close"] - prev_bar["close"]) / prev_bar["close"]
        if change > MAX_PRICE_JUMP_PCT:
            return False, f"價格跳空 {change:.1%}"
        if bar.get("vol", 1) == 0:
            return False, "成交量為零"
    except Exception:
        pass
    return True, ""
