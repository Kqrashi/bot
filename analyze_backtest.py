import sys
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib

if len(sys.argv) < 2:
    print("Usage: python analyze_backtest.py <path_to_csv>")
    sys.exit(1)

df = pd.read_csv(sys.argv[1])

COL = "pnl_net_pct"
if COL not in df.columns:
    if "pnl" in df.columns:
        COL = "pnl"
    else:
        print(f"[ERROR] 找不到損益欄位（pnl_net_pct 或 pnl），請確認 CSV 格式")
        sys.exit(1)

# 1. 總損益
total_pnl = df[COL].sum()
print(f"總損益（Total PnL）: {total_pnl:.4f}")

# 2. 勝率
win_rate = (df[COL] > 0).mean()
print(f"勝率（Win Rate）: {win_rate*100:.2f}%")

# 3. 平均單筆盈虧
avg_pnl = df[COL].mean()
print(f"平均每筆盈虧: {avg_pnl:.4f}")

# 4. 最大連續虧損
def max_consecutive_losses(pnl_series):
    loss_streak, max_streak = 0, 0
    for x in pnl_series:
        if x < 0:
            loss_streak += 1
            max_streak = max(max_streak, loss_streak)
        else:
            loss_streak = 0
    return max_streak

max_loss_streak = max_consecutive_losses(df[COL])
print(f"最大連續虧損單數: {max_loss_streak}")

# 5. 最大回撤
def max_drawdown(pnls):
    equity = pnls.cumsum()
    high_water_mark = equity.cummax()
    drawdowns = high_water_mark - equity
    return drawdowns.max()

max_dd = max_drawdown(df[COL])
print(f"最大回撤: {max_dd:.4f}")

# 分級分析
if "entry_level" in df.columns:
    group = df.groupby("entry_level")
    result = group.agg(
        trade_count=(COL, "count"),
        win_rate=(COL, lambda x: (x > 0).mean()),
        avg_pnl=(COL, "mean")
    )
    print("\n分級(A/B/AB)統計：")
    print(result)
else:
    print("未發現 entry_level 欄位，請確認回測有寫入級別！")

matplotlib.rcParams['font.sans-serif'] = ['Microsoft JhengHei']
matplotlib.rcParams['axes.unicode_minus'] = False

df["equity"] = df[COL].cumsum()
df["equity"].plot(title="策略損益曲線")
plt.xlabel("交易次數")
plt.ylabel("累積損益")
plt.show()
