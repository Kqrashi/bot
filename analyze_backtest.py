import pandas as pd
import matplotlib.pyplot as plt
import matplotlib

# 讀取 trade log csv
df = pd.read_csv("backtest_results/backtest_BTC_USDT_smc.csv")

# 1. 總損益
total_pnl = df["pnl"].sum()
print(f"總損益（Total PnL）: {total_pnl:.2f}")

# 2. 勝率
win_rate = (df["pnl"] > 0).mean()
print(f"勝率（Win Rate）: {win_rate*100:.2f}%")

# 3. 平均單筆盈虧
avg_pnl = df["pnl"].mean()
print(f"平均每筆盈虧: {avg_pnl:.2f}")

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

max_loss_streak = max_consecutive_losses(df["pnl"])
print(f"最大連續虧損單數: {max_loss_streak}")

# 5. 最大回撤
def max_drawdown(pnls):
    equity = pnls.cumsum()
    high_water_mark = equity.cummax()
    drawdowns = high_water_mark - equity
    return drawdowns.max()

max_dd = max_drawdown(df["pnl"])
print(f"最大回撤: {max_dd:.2f}")

# ============【新增分級分析表】===========
if "entry_level" in df.columns:
    group = df.groupby("entry_level")
    result = group.agg(
        trade_count = ("pnl", "count"),
        win_rate = ("pnl", lambda x: (x > 0).mean()),
        avg_pnl = ("pnl", "mean")
    )
    print("\n分級(A/B/AB)統計：")
    print(result)
else:
    print("未發現 entry_level 欄位，請確認回測有寫入級別！")

# 6. 其他你想看的統計（可以加上）
matplotlib.rcParams['font.sans-serif'] = ['Microsoft JhengHei']  # 微軟正黑體
matplotlib.rcParams['axes.unicode_minus'] = False  # 正確顯示負號

df["equity"] = df["pnl"].cumsum()
df["equity"].plot(title="策略損益曲線")
plt.xlabel("交易次數")
plt.ylabel("累積損益")
plt.show()

