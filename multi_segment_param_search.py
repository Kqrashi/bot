import os
import glob
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
from strategy import SMCStrategy, SMCStrategyLoose


# === 0. 讀取 historical_data 資料夾下全部 .csv 檔 ===
csv_files = glob.glob("historical_data/*.csv")
result_dir = "search_results/segments"
os.makedirs(result_dir, exist_ok=True)

# === 1. 設定參數 ===
tp_r_list = [1.05, 1.1, 1.15, 1.2]
tol_fvg_list = [0.002, 0.003, 0.004, 0.005]
strategy_classes = {
    "smc": SMCStrategy,
    "smc_loose": SMCStrategyLoose
}

for data_path in csv_files:
    print(f"處理檔案：{data_path}")
    symbol = os.path.basename(data_path).replace(".csv", "")
    # === 2. 資料切區段 ===
    df = pd.read_csv(data_path)
    df['datetime'] = pd.to_datetime(df['ts'], unit='s')
    df.set_index('datetime', inplace=True)

    segment_months = 6
    segments = []
    start = df.index.min()
    while start < df.index.max():
        end = start + pd.DateOffset(months=segment_months)
        seg = df.loc[(df.index >= start) & (df.index < end)]
        if len(seg) > 500:
            segments.append((start, end, seg))
        start = end

    # === 3. 多區間自動參數搜尋 ===
    all_summary = []
    for idx, (start, end, seg_df) in enumerate(segments):
        print(f"\n==== 分析區間{idx+1}: {start.strftime('%Y-%m-%d')} ~ {end.strftime('%Y-%m-%d')}（{len(seg_df)} 筆） ====")
        segment_results = []
        for strategy_name, strategy_class in strategy_classes.items():
            for tp_r in tp_r_list:
                for tol_fvg in tol_fvg_list:
                    strategy = strategy_class(tp_r=tp_r, tol_fvg=tol_fvg)
                    trade_logs = []
                    entry = None
                    for i in range(100, len(seg_df)):
                        bars = seg_df.iloc[i-100:i]
                        htf_bars = seg_df.iloc[max(0, i-500):i]
                        bar = bars.iloc[-1]
                        sig, side, info = strategy.check_entry_signal(bar, bars, htf_bars)
                        if sig and entry is None:
                            entry = {
                                "side": side,
                                "entry_price": bar["close"],
                                "stop": info.get("stop", bar["low"]*0.98),
                                "tp": info.get("tp", bar["close"]*tp_r),
                                "entry_time": bar["ts"],
                                "size": 1
                            }
                        elif entry is not None:
                            should_exit = strategy.check_exit_signal(
                                bar, bars, entry["side"], entry["entry_price"], entry["stop"], entry["tp"]
                            )
                            if should_exit:
                                pnl = (bar["close"] - entry["entry_price"]) if entry["side"] == "long" else (entry["entry_price"] - bar["close"])
                                trade_logs.append(pnl)
                                entry = None
                    # 統計結果
                    total_pnl = sum(trade_logs)
                    win_rate = sum([1 for p in trade_logs if p > 0]) / len(trade_logs) if trade_logs else 0
                    segment_results.append({
                        "區間": f"{start.strftime('%Y-%m-%d')}~{end.strftime('%Y-%m-%d')}",
                        "strategy": strategy_name,
                        "tp_r": tp_r,
                        "tol_fvg": tol_fvg,
                        "總損益": total_pnl,
                        "勝率": win_rate,
                        "單數": len(trade_logs)
                    })
        # 本段小表
        seg_df_out = pd.DataFrame(segment_results)
        seg_fname = f"{result_dir}/{symbol}_segment_{idx+1}_{start.strftime('%Y%m%d')}_{end.strftime('%Y%m%d')}.csv"
        seg_df_out.to_csv(seg_fname, index=False, encoding="utf-8-sig")
        print(f"  已輸出 {symbol} 區間績效表：{seg_fname}")
        all_summary.extend(segment_results)

    # === 4. 匯出總績效總表 ===
    summary_path = f"{result_dir}/{symbol}_rolling_param_search_summary.csv"
    summary_df.to_csv(summary_path, index=False, encoding="utf-8-sig")
    print(f"\n[{symbol}] 所有區間回測與參數搜尋已完成！總績效表已輸出：{summary_path}")

    # === 5. 畫Heatmap與最佳參數分布 ===
    for seg_name in summary_df['區間'].unique():
        for strat in summary_df['strategy'].unique():
            df_seg = summary_df[(summary_df['區間']==seg_name) & (summary_df['strategy']==strat)]
            if df_seg.empty: continue
            heatmap_data = df_seg.pivot(index='tp_r', columns='tol_fvg', values='總損益')
            heatmap_path = f"{result_dir}/{symbol}_heatmap_{strat}_{seg_name.replace('~','_')}.png"
            plt.figure(figsize=(6,4))
            sns.heatmap(heatmap_data, annot=True, fmt=".0f", cmap='coolwarm')
            plt.title(f"{strat} 績效Heatmap\n({seg_name})")
            plt.ylabel("tp_r")
            plt.xlabel("tol_fvg")
            plt.tight_layout()
            plt.savefig(heatmap_path)
            plt.close()
            print(f"  已輸出 {symbol} heatmap：{heatmap_path}")

    # === 6. 每段最佳參數與分布表 ===
    best_params_path = f"{result_dir}/{symbol}_best_params_by_segment.csv"
    best_params = summary_df.groupby(['區間','strategy']).apply(
        lambda x: x.sort_values('總損益', ascending=False).iloc[0]
    ).reset_index(drop=True)
    best_params.to_csv(best_params_path, index=False, encoding='utf-8-sig')
    print(f"\n[{symbol}] 已輸出每區間最佳參數分布表：{best_params_path}")
    print(best_params[['區間','strategy','tp_r','tol_fvg','總損益','勝率','單數']])

    # === 7. Walk-Forward測試 ===
    walkforward_logs = []
    for i in range(1, len(segments)):
        for strat in strategy_classes.keys():
            prev_seg = segments[i-1]
            this_seg = segments[i]
            prev_name = f"{prev_seg[0].strftime('%Y-%m-%d')}~{prev_seg[1].strftime('%Y-%m-%d')}"
            this_name = f"{this_seg[0].strftime('%Y-%m-%d')}~{this_seg[1].strftime('%Y-%m-%d')}"
            prev_best = best_params[(best_params['區間']==prev_name) & (best_params['strategy']==strat)]
            if prev_best.empty: continue
            best_tp_r = prev_best['tp_r'].values[0]
            best_tol_fvg = prev_best['tol_fvg'].values[0]
            seg_df = this_seg[2]
            strategy_class = strategy_classes[strat]
            strategy = strategy_class(tp_r=best_tp_r, tol_fvg=best_tol_fvg)
            trade_logs = []
            entry = None
            for j in range(100, len(seg_df)):
                bars = seg_df.iloc[j-100:j]
                htf_bars = seg_df.iloc[max(0, j-500):j]
                bar = bars.iloc[-1]
                sig, side, info = strategy.check_entry_signal(bar, bars, htf_bars)
                if sig and entry is None:
                    entry = {
                        "side": side,
                        "entry_price": bar["close"],
                        "stop": info.get("stop", bar["low"]*0.98),
                        "tp": info.get("tp", bar["close"]*best_tp_r),
                        "entry_time": bar["ts"],
                        "size": 1
                    }
                elif entry is not None:
                    should_exit = strategy.check_exit_signal(
                        bar, bars, entry["side"], entry["entry_price"], entry["stop"], entry["tp"]
                    )
                    if should_exit:
                        pnl = (bar["close"] - entry["entry_price"]) if entry["side"] == "long" else (entry["entry_price"] - bar["close"])
                        trade_logs.append(pnl)
                        entry = None
            total_pnl = sum(trade_logs)
            win_rate = sum([1 for p in trade_logs if p > 0]) / len(trade_logs) if trade_logs else 0
            walkforward_logs.append({
                "應用區間": this_name,
                "策略": strat,
                "tp_r": best_tp_r,
                "tol_fvg": best_tol_fvg,
                "總損益": total_pnl,
                "勝率": win_rate,
                "單數": len(trade_logs)
            })

    walkforward_path = f"{result_dir}/{symbol}_walk_forward_results.csv"
    walk_df = pd.DataFrame(walkforward_logs)
    walk_df.to_csv(walkforward_path, index=False, encoding='utf-8-sig')
    print(f"\n[{symbol}] 已輸出 Walk-Forward 結果表：{walkforward_path}")
    print(walk_df)

    print(f"\n[{symbol}] 全部分析完成！每個區間績效表、最佳參數表、Heatmap與Walk-Forward全自動生成。")
    print("="*50)