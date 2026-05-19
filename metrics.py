import math


def compute_metrics(trade_logs: list):
    """
    trade_logs: list of float (percentage return, already net of fees)
    returns: (sharpe, max_drawdown, profit_factor)
    """
    n = len(trade_logs)

    # Sharpe: n < 5 樣本不足，drawdown/profit_factor 仍計算
    if n < 5:
        sharpe = float("nan")
    else:
        mean = sum(trade_logs) / n
        variance = sum((p - mean) ** 2 for p in trade_logs) / n
        std = math.sqrt(variance)
        sharpe = (mean / std * math.sqrt(252)) if std > 0 else float("nan")

    # Max Drawdown: peak=None 初始化避免 tiny-peak 造成超大值，上限 1.0
    if n == 0:
        return float("nan"), 0.0, float("nan")
    else:
        cumulative = 0.0
        peak = None
        max_dd = 0.0
        for pnl in trade_logs:
            cumulative += pnl
            if peak is None or cumulative > peak:
                peak = cumulative
            if peak is not None and peak > 0:
                dd = (peak - cumulative) / peak
                if dd > max_dd:
                    max_dd = dd
        max_drawdown = min(max_dd, 1.0)

    gains = sum(p for p in trade_logs if p > 0)
    losses = sum(p for p in trade_logs if p < 0)
    profit_factor = (gains / abs(losses)) if losses < 0 else float("inf")

    return sharpe, max_drawdown, profit_factor
