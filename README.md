# 自動交易系統操作手冊

## 1. 專案簡介

本專案支援多幣多策略自動交易，具備：
- 多策略模組（SMC、SMC+趨勢過濾等）
- 動態風控與自動資金權重調整
- 容錯機制、自動停單/異常報警
- 每日自動 trade log、每週績效報告
- 支援多幣種、多週期、多策略 plug & play
- 回測功能（可驗證實盤績效）

---

## 2. 依賴安裝

請先安裝 python 3.8 以上版本。

安裝必要套件：

```bash
pip install -r requirements.txt

---

## 3. 專案結構說明

├─ README.md                        # 操作手冊（本檔案）
├─ main.py                          # 主程式，多幣多策略交易與紀錄
├─ config.py                        # 全域參數設定、策略參數、資料夾定義
├─ exchange_helper.py               # API 封裝與快取
├─ strategy.py                      # SMC、SMC+Trend等策略 plug-in
├─ strategy_periodic.py             # 週期專屬策略模組
├─ backtest.py                      # 多策略多幣回測
├─ risk.py                          # 多策略動態風控、自動權重調整、停單
├─ requirements.txt                 # 套件需求列表
├─ trade_logs/                      # 每日自動紀錄交易資料
├─ trade_log_backups/               # 備份
├─ reports/                         # 每週自動績效報告
├─ download_ohlcv_multi.py          # 抓取歷史資料
├─ analyze_backtest.py              # 回測數據整理成圖表
├─ param_search.py                  # 自動化多參數搜尋腳本範本(有下面那個之後其實可以不用這個了)
└─ multi_segment_param_search.py    # 多區間自動參數優化

4. 快速啟動

    1.API金鑰設定
    請在 exchange_helper.py 填入你的 OKX API Key/Secret/Password。

    2.參數調整
    編輯 config.py 設定交易幣種、策略參數、週期、風控規則。

    3.啟動自動交易
    python main.py
    交易紀錄會自動存在 trade_logs/，遇到異常會有備份與錯誤提醒。

    4.執行回測
    請將歷史K線CSV放入 historical_data/
    python backtest.py


5. 策略擴充教學

    在 strategy.py 新增你的策略 class（需實作 check_entry_signal 和 check_exit_signal 方法）

    在 STRATEGY_MAP 註冊新策略名稱與對應物件

    到 config.py 的 STRATEGY_PARAMS 加入新策略參數設定


6. 風控、停單、權重動態調整

    risk.py 會依策略近50筆勝率與最大回撤自動調整資金比重

    達到最大回撤/連續虧損會自動暫停該策略下單，異常自動報警

    所有狀態都會 print 並記錄於 trade log，方便debug與稽核


7. 績效報告

    每週自動統計策略績效並存於 reports/

    內容包含每策略/每幣損益、勝率、最大回撤


8. 重要提醒

    請定期備份所有 log 資料與報告

    嚴格遵守 OKX API 使用規範，勿超頻下單

    請依所在地法律規定申報稅務、合規操作

    若需異常通知/自動email/Line報警，可於 main.py/risk.py 介面延伸


9. 常見問題

Q1. 如何加新策略？

    參照 strategy.py 內部範例，新增class並於 STRATEGY_MAP 註冊即可。

Q2. API金鑰如何保管？

    請勿外流 .env 檔或直接上傳程式碼到公開平台。

Q3. 回測為何需要csv？

    因為回測採用本地歷史K線進行多策略測試，需手動或自動下載K線。

Q4. 系統遇到重大異常會怎麼辦？

    會自動暫停交易、備份資料、顯示錯誤訊息並等待人工處理。




