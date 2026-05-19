# risk.py
import pandas as pd
import os
from logger import get_logger

_log = get_logger(__name__)

class RiskEngine:
    def __init__(self, equity=1000, risk_pct=0.01):
        self.equity = equity
        self.risk_pct = risk_pct
        self.strategy_weights = {}  # 每個策略動態資金分配
        self.paused_strategies = set()
        self.max_drawdown_pct = 0.2
        self.max_consecutive_loss = 4
        self.strategy_stats = {}

    def on_new_trade(self, trade_request, strategy_name="default"):
        if strategy_name in self.paused_strategies:
            _log.warning(f"策略{strategy_name}已暫停，不下單")
            return 0
        # 信號分級，動態分配部位
        level = None
        if trade_request and "level" in trade_request:
            level = trade_request["level"]
        # 定義各等級投入比例
        level_risk = {"A": 0.03, "AB": 0.02, "B": 0.01, "C": 0.003}  # A 3%、AB 2%、B 1%、C 0.3%
        pct = level_risk.get(level, self.risk_pct)  # 預設風控比例
        size = self.equity * pct * self.get_strategy_weight(strategy_name)
        return size

    def get_strategy_weight(self, strategy_name):
        return self.strategy_weights.get(strategy_name, 1.0)

    def update_strategy_weights(self, trade_log_path, window=50):
        if not os.path.isfile(trade_log_path):
            return
        df = pd.read_csv(trade_log_path)
        for strategy in df['strategy'].unique():
            strat_df = df[df['strategy'] == strategy].tail(window)
            winrate = (strat_df['pnl'] > 0).sum() / len(strat_df) if len(strat_df) > 0 else 0
            drawdown = self._compute_drawdown(strat_df['pnl'])
            degrading = False
            degradation_score = 0.0
            if len(strat_df) >= 20:
                recent_wr = strat_df.tail(20)['pnl'].gt(0).mean()
                older = strat_df.iloc[-50:-20] if len(strat_df) >= 50 else strat_df.iloc[:-20]
                older_wr = older['pnl'].gt(0).mean() if len(older) > 0 else recent_wr
                degradation_score = round(float(older_wr - recent_wr), 4)
                degrading = degradation_score > 0.15
                if degrading:
                    _log.warning(f"策略{strategy}偵測到退化，degradation_score={degradation_score:.2f}")

            self.strategy_stats[strategy] = {
                "winrate": winrate,
                "drawdown": drawdown,
                "consecutive_loss": self._compute_consecutive_loss(strat_df['pnl']),
                "degrading": degrading,
                "degradation_score": degradation_score
            }
            # 動態權重算法
            if winrate > 0.6:
                self.strategy_weights[strategy] = 1.5
            elif winrate < 0.45:
                self.strategy_weights[strategy] = 0.5
            else:
                self.strategy_weights[strategy] = 1.0
            # 自動停單條件
            if drawdown > self.max_drawdown_pct or self.strategy_stats[strategy]['consecutive_loss'] >= self.max_consecutive_loss:
                self.paused_strategies.add(strategy)
                _log.warning(f"策略{strategy}已達停單條件，暫停交易！")
            else:
                self.paused_strategies.discard(strategy)

    @staticmethod
    def _compute_drawdown(pnl_series):
        cum_pnl = pnl_series.cumsum()
        peak = cum_pnl.cummax()
        dd = (peak - cum_pnl).max()
        dd_pct = dd / peak.max() if peak.max() > 0 else 0
        return dd_pct

    @staticmethod
    def _compute_consecutive_loss(pnl_series):
        loss = (pnl_series < 0).astype(int)
        return RiskEngine._max_consecutive_ones(loss.values)

    @staticmethod
    def _max_consecutive_ones(arr):
        max_count = count = 0
        for v in arr:
            count = count + 1 if v == 1 else 0
            max_count = max(max_count, count)
        return max_count
