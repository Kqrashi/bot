# config.py
# 專案全局參數與多幣多策略設定
from strategy_periodic import FiveMinStrategy, FifteenMinStrategy, ThirtyMinStrategy, OneHourStrategy, FourHourStrategy
from constants import ALLOWED_LEVELS_MAP

SYMBOLS = ["BTC/USDT"]  # 你要交易的幣種清單，可擴充 #, "ETH/USDT"
TIMEFRAME = "5m"  # 主要運行週期，可在 main.py 迴圈中對不同策略/幣種彈性調整
START_EQUITY = 1000  # 初始資金（用於risk與回測）

# 策略參數範例，key: 策略名稱
STRATEGY_PARAMS = {
    "smc": {
        "lookback": 3,
        "tol_fvg": 0.004,
        "tp_r": 1.2
    },
    "smc_trend": {
        "lookback": 3,
        "tol_fvg": 0.004,
        "tp_r": 1.2,
        "trend_ma_fast": 20,
        "trend_ma_slow": 60,
        "trend_filter": True
    },
    # 你要加新策略只要多一個key即可
}

# 週期專屬策略對應（推薦寫法）
STRATEGY_PERIODIC_MAP = {
    "5m": FiveMinStrategy,
    "15m": FifteenMinStrategy,
    "30m": ThirtyMinStrategy,
    "1h": OneHourStrategy,
    "4h": FourHourStrategy,
}

# 這個你可依未來回測再優化
STRATEGY_PERIODIC_PARAMS = {
    "5m":  {"tp_r": 1.01, "tol_fvg": 0.0015},
    "15m": {"tp_r": 1.10, "tol_fvg": 0.0015},
    "30m": {"tp_r": 1.13, "tol_fvg": 0.002},
    "1h":  {"tp_r": 1.18, "tol_fvg": 0.0025},
    "4h":  {"tp_r": 1.22, "tol_fvg": 0.0025},
    "1d":  {"tp_r": 1.35, "tol_fvg": 0.003},
}

ALLOWED_LEVELS_MAP = {
    "5m":  ["A", "AB", "B", "C"],
    "15m": ["A", "AB", "B"],
    "30m": ["A", "AB"],
    "1h":  ["A", "AB"],
    "4h":  ["A", "AB"],
    "1d":  ["A"],     # 如果你有日線策略
}

# 風控參數（可後續由RiskEngine讀取）
RISK_PARAMS = {
    "max_drawdown_pct": 0.2,  # 20%最大回撤時暫停
    "max_consecutive_loss": 4,  # 連續虧損次數
    "risk_pct": 0.01           # 單單風險佔比
}

# 報告/資料夾
REPORT_DIR = "reports"
TRADE_LOG_DIR = "trade_logs"
BACKUP_DIR = "trade_log_backups"
