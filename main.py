# main.py
import os
import time
import json
import pandas as pd
from datetime import datetime

import config
from config import SYMBOLS, TIMEFRAME, STRATEGY_PARAMS, RISK_PARAMS, TRADE_LOG_DIR, BACKUP_DIR, START_EQUITY, FEE_RATE

if config.STRATEGY_MODE == "periodic":
    from strategy_periodic import STRATEGY_PERIODIC_MAP as STRATEGY_MAP
else:
    from strategy import STRATEGY_MAP

from exchange_helper import ExchangeHelper
from risk import RiskEngine
from logger import get_logger
from notifier import notify_trade_open, notify_trade_close, notify_error
from data_guard import check_bar_quality
from bot_command import start_command_listener

logger = get_logger(__name__)

STATE_FILE = "open_trades_state.json"


def get_current_session() -> str:
    hour = datetime.utcnow().hour
    if 0 <= hour < 8:
        return "asia"
    if 7 <= hour < 16:
        return "london"
    if 12 <= hour < 21:
        return "ny"
    return "off"


def _save_open_trades(open_trades: dict) -> None:
    try:
        serializable = {f"{k[0]}|{k[1]}": v for k, v in open_trades.items()}
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(serializable, f, ensure_ascii=False, default=str)
    except Exception as e:
        logger.warning(f"寫入 open_trades 狀態失敗: {e}")


def _load_open_trades() -> dict:
    if not os.path.isfile(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return {tuple(k.split("|", 1)): v for k, v in raw.items()}
    except Exception as e:
        logger.warning(f"讀取 open_trades 狀態失敗，從空白開始: {e}")
        return {}


def _reconcile_positions(exchange, open_trades: dict) -> None:
    try:
        positions = exchange.exchange.fetch_positions()
        live = {p["symbol"] for p in positions if float(p.get("contracts", 0) or 0) > 0}
    except Exception as e:
        logger.warning(f"對帳失敗，跳過: {e}")
        return
    stale = [k for k in open_trades if k[0] not in live]
    for k in stale:
        logger.warning(f"清除孤立持倉記錄（交易所已無此倉）: {k}")
        del open_trades[k]
    if stale:
        _save_open_trades(open_trades)


def safe_append_to_csv(trade_record, csv_path, backup_path=None, max_retry=3):
    for attempt in range(max_retry):
        try:
            df = pd.DataFrame([trade_record])
            file_exists = os.path.isfile(csv_path)
            df.to_csv(csv_path, mode="a", header=not file_exists, index=False)
            if backup_path:
                file_exists_bak = os.path.isfile(backup_path)
                df.to_csv(backup_path, mode="a", header=not file_exists_bak, index=False)
            return True
        except Exception as e:
            logger.warning(f"寫入csv失敗: {e}")
            time.sleep(2)
    logger.error("多次嘗試寫檔失敗，資料暫存buffer等待下次寫入！")
    return False


def main():
    exchange = ExchangeHelper()
    risk = RiskEngine(equity=START_EQUITY, risk_pct=RISK_PARAMS.get("risk_pct", 0.01))
    open_trades = _load_open_trades()
    _reconcile_positions(exchange, open_trades)

    start_command_listener(risk, exchange)

    try:
        from notifier import notify
        notify("🔄 Bot 已啟動")
    except Exception:
        pass

    trade_records_buffer = []
    daily_pnl = 0.0
    daily_date = datetime.utcnow().date()

    while True:
        logger.info("進入主迴圈...")

        if risk.global_halt:
            logger.info("全局熔斷中，等待重置...")
            time.sleep(60)
            continue

        try:
            today = datetime.now()
            today_utc = datetime.utcnow().date()
            if today_utc != daily_date:
                daily_pnl = 0.0
                daily_date = today_utc

            month_folder = today.strftime("%Y-%m")
            today_str = today.strftime("%Y-%m-%d")
            base_dir = TRADE_LOG_DIR
            save_dir = os.path.join(base_dir, month_folder)
            os.makedirs(save_dir, exist_ok=True)
            os.makedirs(BACKUP_DIR, exist_ok=True)
            csv_path = os.path.join(save_dir, f"trade_log_{today_str}.csv")
            backup_path = os.path.join(BACKUP_DIR, f"trade_log_backup_{today_str}.csv")

            if int(time.time()) % 3600 < 20:
                risk.update_strategy_weights(csv_path, window=50)

            for symbol in SYMBOLS:
                logger.debug(f"正在處理幣種: {symbol}")
                bars = exchange.fetch_ohlcv(symbol, TIMEFRAME, limit=100)
                bar = bars.iloc[-1].to_dict()
                prev_bar = bars.iloc[-2].to_dict() if len(bars) > 1 else None

                ok, reason = check_bar_quality(bar, prev_bar)
                if not ok:
                    logger.warning(f"{symbol} bar品質異常: {reason}，跳過此輪")
                    notify_error(f"{symbol} bar品質異常", Exception(reason))
                    continue

                htf_bars = exchange.fetch_ohlcv(symbol, "1h", limit=100)
                oi_df = exchange.fetch_oi_history(symbol, TIMEFRAME, limit=50)

                for strategy_name, strategy in STRATEGY_MAP.items():
                    logger.debug(f"策略: {strategy_name} 準備檢查訊號")
                    key = (symbol, strategy_name)
                    entry = open_trades.get(key, None)

                    params = STRATEGY_PARAMS.get(strategy_name, {})
                    sig, side, info = strategy.check_entry_signal(bar, bars, htf_bars, oi_df=oi_df, bars_for_cvd=bars, **params)

                    if sig and entry is None:
                        stop_price = info.get("stop", bar["low"] * 0.98 if side == "long" else bar["high"] * 1.02)
                        tp_price = info.get("tp", None)
                        size_usdt = risk.on_new_trade(info, strategy_name=strategy_name)
                        if size_usdt and size_usdt > 0:
                            contract_sz = config.CONTRACT_SIZE.get(symbol, 0.01)
                            size_contracts = round(size_usdt / bar["close"] / contract_sz, 4)
                            if size_contracts <= 0:
                                logger.warning(f"{symbol} size_contracts={size_contracts}，跳過下單")
                                continue
                            order = exchange.open_position(symbol, side, size_contracts)
                            if order is None:
                                logger.error(f"{symbol} [{strategy_name}] open_position 失敗，跳過")
                                continue
                            open_trades[key] = {
                                "side": side,
                                "entry_price": bar["close"],
                                "stop": stop_price,
                                "tp": tp_price,
                                "entry_time": bar["ts"],
                                "order_id": order["id"],
                                "size": size_contracts,
                                "level": info.get("level"),
                                "fvg_mid": info.get("fvg_mid"),
                                "ob_low": info.get("ob_low"),
                                "ob_high": info.get("ob_high"),
                                "cvd_now": info.get("cvd_now"),
                                "oi_rising": info.get("oi_rising"),
                                "strategy_params": f"tp_r={getattr(strategy, 'tp_r', '')},tol_fvg={getattr(strategy, 'tol_fvg', '')}",
                            }
                            _save_open_trades(open_trades)
                            logger.info(f"Open {symbol} [{strategy_name}]: {side}, size: {size_contracts} contracts, entry: {bar['close']}")
                            notify_trade_open(symbol, strategy_name, side, bar["close"], size_contracts)

                    if entry is not None:
                        should_exit, exit_reason = strategy.check_exit_signal(
                            bar, bars,
                            entry.get("side"), entry.get("entry_price"),
                            entry.get("stop"), entry.get("tp")
                        )
                        if should_exit:
                            close_result = exchange.close_position(symbol, entry["side"], entry["size"])
                            if close_result is None:
                                logger.error(f"{symbol} [{strategy_name}] close_position 失敗，保留持倉記錄等待下輪")
                                continue
                            close_time = bar["ts"]
                            close_price = bar["close"]
                            pnl = (close_price - entry["entry_price"]) * entry["size"] if entry["side"] == "long" \
                                else (entry["entry_price"] - close_price) * entry["size"]
                            fee = entry["entry_price"] * entry["size"] * FEE_RATE * 2
                            pnl_net = pnl - fee
                            risk.equity += pnl_net
                            daily_pnl += pnl_net
                            risk.check_daily_loss(daily_pnl)
                            logger.info(f"equity 更新為 {risk.equity:.2f}（本筆 pnl={pnl:.2f}, fee={fee:.4f}, pnl_net={pnl_net:.2f}, reason={exit_reason}）")
                            trade_record = {
                                "symbol": symbol,
                                "strategy": strategy_name,
                                "side": entry["side"],
                                "entry_time": entry["entry_time"],
                                "entry_price": entry["entry_price"],
                                "stop": entry["stop"],
                                "tp": entry["tp"],
                                "size": entry["size"],
                                "exit_time": close_time,
                                "exit_price": close_price,
                                "pnl": pnl,
                                "fee": round(fee, 6),
                                "pnl_net": round(pnl_net, 6),
                                "session": get_current_session(),
                                "order_id": entry["order_id"],
                                "reason": exit_reason,
                                "entry_level": entry.get("level"),
                                "fvg_mid": entry.get("fvg_mid"),
                                "ob_zone": f"{entry.get('ob_low')}-{entry.get('ob_high')}",
                                "cvd_now": entry.get("cvd_now"),
                                "oi_rising": entry.get("oi_rising"),
                                "strategy_params": entry.get("strategy_params"),
                            }
                            ok = safe_append_to_csv(trade_record, csv_path, backup_path)
                            if not ok:
                                trade_records_buffer.append(trade_record)
                            else:
                                if trade_records_buffer:
                                    logger.info(f"補寫 {len(trade_records_buffer)} 筆buffer資料")
                                    for rec in trade_records_buffer:
                                        safe_append_to_csv(rec, csv_path, backup_path)
                                    trade_records_buffer.clear()
                            logger.info(f"Closed {symbol} [{strategy_name}] position, reason={exit_reason}, logged to {csv_path}")
                            notify_trade_close(symbol, strategy_name, pnl_net, reason=exit_reason)
                            del open_trades[key]
                            _save_open_trades(open_trades)

        except Exception as e:
            logger.error(f"主流程異常: {e}")
            notify_error("main loop", e)
            time.sleep(60)
            continue

        time.sleep(15)

if __name__ == "__main__":
    main()
