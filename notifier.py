# notifier.py — Telegram 即時通報，失敗靜默不影響主流程
import os
import requests
from dotenv import load_dotenv
from logger import get_logger

load_dotenv()
_log = get_logger(__name__)

_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
_API = f"https://api.telegram.org/bot{_TOKEN}/sendMessage"


def _enabled():
    try:
        from config import TELEGRAM_ENABLED
        return TELEGRAM_ENABLED
    except Exception:
        return False


def notify(msg: str) -> None:
    if not _enabled() or not _TOKEN or not _CHAT_ID:
        return
    try:
        requests.post(_API, json={"chat_id": _CHAT_ID, "text": msg}, timeout=5)
    except Exception as e:
        _log.warning(f"Telegram 通報失敗: {e}")


def notify_trade_open(symbol: str, strategy: str, side: str, entry_price: float, size: float) -> None:
    side_emoji = "🟢" if side == "long" else "🔴"
    notify(
        f"{side_emoji} 開倉\n"
        f"幣種：{symbol}\n"
        f"策略：{strategy}\n"
        f"方向：{side.upper()}\n"
        f"進場價：{entry_price:.4f}\n"
        f"倉位：{size:.4f}"
    )


def notify_trade_close(symbol: str, strategy: str, pnl_net: float, reason: str = "") -> None:
    emoji = "✅" if pnl_net >= 0 else "❌"
    sign = "+" if pnl_net >= 0 else ""
    notify(
        f"{emoji} 平倉\n"
        f"幣種：{symbol}\n"
        f"策略：{strategy}\n"
        f"淨損益：{sign}{pnl_net:.4f}\n"
        f"原因：{reason or 'TP/SL/BMS'}"
    )


def notify_strategy_paused(strategy: str, reason: str = "") -> None:
    notify(
        f"⚠️ 策略暫停\n"
        f"策略：{strategy}\n"
        f"原因：{reason or '達停單條件'}"
    )


def notify_error(context: str, error: Exception) -> None:
    notify(
        f"🚨 主流程異常\n"
        f"位置：{context}\n"
        f"錯誤：{type(error).__name__}: {error}"
    )
