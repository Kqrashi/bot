import math


def compute_metrics(trade_logs: list):
    """
    trade_logs: list of float (percentage return, already net of fees)
    returns: (sharpe, max_drawdown, profit_factor)
    """
    n = len(trade_logs)
    if n < 2:
        return float("nan"), float("nan"), float("nan")

    mean = sum(trade_logs) / n
    variance = sum((p - mean) ** 2 for p in trade_logs) / (n - 1)
    std = variance ** 0.5
    sharpe = (mean / std * (n ** 0.5)) if std > 0 else float("nan")

    cumulative = 0.0
    peak = float("-inf")
    max_dd = 0.0
    for pnl in trade_logs:
        cumulative += pnl
        if cumulative > peak:
            peak = cumulative
        if peak > 0:
            dd = (peak - cumulative) / peak
            if dd > max_dd:
                max_dd = dd
    max_drawdown = max_dd

    gains = sum(p for p in trade_logs if p > 0)
    losses = sum(p for p in trade_logs if p < 0)
    profit_factor = (gains / abs(losses)) if losses < 0 else float("inf")

    return sharpe, max_drawdown, profit_factor
