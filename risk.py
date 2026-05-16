# risk.py
import pandas as pd
import os

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
            print(f"[WARN] 策略{strategy_name}已暫停，不下單")
            return 0
        # 信號分級，動態分配部位
        level = None
        if trade_request and "level" in trade_request:
            level = trade_request["level"]
        # 定義各等級投入比例
        level_risk = {"A": 0.03, "B": 0.01, "C": 0.003}  # 最高3%、中1%、最低0.3%
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
            self.strategy_stats[strategy] = {
                "winrate": winrate,
                "drawdown": drawdown,
                "consecutive_loss": self._compute_consecutive_loss(strat_df['pnl'])
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
                print(f"[RISK] 策略{strategy}已達停單條件，暫停交易！")
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
