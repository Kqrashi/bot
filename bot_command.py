# bot_command.py — Telegram 雙向命令，daemon thread 輪詢
import os
import threading
import time
import requests
from logger import get_logger

_log = get_logger(__name__)


def _get_updates(token: str, offset: int) -> list:
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    try:
        r = requests.get(url, params={"offset": offset, "timeout": 10}, timeout=15)
        return r.json().get("result", [])
    except Exception as e:
        _log.warning(f"getUpdates 失敗: {e}")
        return []


def _send(token: str, chat_id: str, text: str) -> None:
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=5,
        )
    except Exception as e:
        _log.warning(f"command reply 失敗: {e}")


def start_command_listener(risk_engine, exchange) -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        _log.info("Telegram token/chat_id 未設定，略過命令監聽")
        return

    def _loop():
        offset = 0
        while True:
            updates = _get_updates(token, offset)
            for u in updates:
                offset = u["update_id"] + 1
                text = u.get("message", {}).get("text", "").strip()
                if text == "/status":
                    halted = "是" if risk_engine.global_halt else "否"
                    paused = ", ".join(risk_engine.paused_strategies) or "無"
                    _send(token, chat_id,
                          f"📊 狀態\n全局停止: {halted}\n暫停策略: {paused}\n權益: {risk_engine.equity:.2f} USDT")
                elif text == "/pause":
                    risk_engine.pause_all()
                    _send(token, chat_id, "⏸ 已暫停所有策略")
                elif text == "/resume":
                    risk_engine.resume_all()
                    _send(token, chat_id, "▶️ 已恢復所有策略")
                elif text == "/equity":
                    _send(token, chat_id, f"💰 帳戶權益: {risk_engine.equity:.2f} USDT")
            time.sleep(3)

    threading.Thread(target=_loop, daemon=True).start()
    _log.info("Telegram 命令監聽已啟動")
