# indicators.py — pure math indicators, no exchange dependency


def calc_cvd(bars, lookback=20):
    """Cumulative Volume Delta over the last `lookback` bars.
    Returns (cvd_now, cvd_change) as floats.
    """
    if bars is None or len(bars) < lookback:
        return (0.0, 0.0)
    delta = bars.apply(
        lambda r: r["vol"] if r["close"] > r["open"] else (-r["vol"] if r["close"] < r["open"] else 0.0),
        axis=1
    )
    cum = delta.cumsum()
    cvd_now = cum.iloc[-1]
    cvd_change = cum.iloc[-1] - cum.iloc[-lookback]
    return (float(cvd_now), float(cvd_change))
