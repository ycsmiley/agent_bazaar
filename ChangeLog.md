# ChangeLog

## 2026-05-03 21:21:54 CST

- 修正 demo 第一眼仍像流程教材的問題，移除頂部 `1-5` flow strip 與所有 `Step` 式標題。
- 將 `demo/market-trace.html` 頂部改成產品式 `Agent marketplace dashboard`，集中顯示 live sellers、open quotes、current deal、SDK quickstart command 與 active inventory。
- 將 buyer / seller 面板文案改成產品操作語言：`Buy work from the agent market`、`Publish seller capacity`，避免看起來像逐步教學頁。
- 壓縮 dashboard 成單一卡片，半螢幕 demo 第一屏可同時看到市場狀態、SDK 串接入口與 buyer RFQ 操作，不再被流程卡占滿。
- 半螢幕瀏覽器驗證通過：畫面不再出現 flow card / Step 標籤，第一眼更像 agent marketplace console。

## 2026-05-03 21:14:23 CST

- 補上外部 agent 開箱即用串接路徑，避免產品只看得到內建 buyer / seller，而看不到其他 agent 如何加入市場。
- 新增 `agents/sdk.py`，提供 `AgentBazaarSeller`、`AgentBazaarConfig`、`SellerListing`，可建立 agent identity、輸出 integration config、發布 seller listing，並用 handler 產生 signed delivery。
- 新增 `examples/seller_sdk_quickstart.py`，外部 agent 可用 `PYTHONPATH=. python examples/seller_sdk_quickstart.py` 發布可媒合的 SDK seller，並跑一次 delivery smoke test。
- 更新 `scripts/serve_trade_playback.py`，讓 `/api/listings` 保留 SDK 傳入的 `agent_id` 與 `agent_public_key`，demo market 會顯示真實外部 agent identity。
- 更新 `README.md` 與 `demo/README.md`，補上 service-backed demo 搭配 SDK seller 的操作路徑，讓評審能看到 agent onboarding 不是封閉假資料。
- 新增 `tests/test_sdk.py`，驗證 integration config、listing publish payload、signed delivery；本次 `pytest tests/test_sdk.py -q` 與相關 ruff check 均通過。

## 2026-05-03 21:10:26 CST

- 將 buyer demo 從「按一次直接完成」改成分步產品操作，避免看起來只是播放流程或假 demo。
- `demo/market-trace.html` 現在會依序呈現 `Send RFQ to market`、`Run market matching`、`Notify seller to execute`、`Verify delivery and release`，每一步都有不同狀態與摘要。
- Delivery payload、hash 與 payment release 不再一開始就全部露出；seller 尚未執行前會顯示 pending，seller 回傳後仍需 buyer 驗證才顯示 payment release。
- Marketplace flow strip 會跟著 buyer stage 逐步亮起，讓畫面看起來是正在操作交易，而不是單純把流程卡片放上去。
- 半螢幕瀏覽器驗證通過：buyer 端可依序看到 RFQ、matching、seller working、delivery ready、settled 的按鈕與狀態變化。

## 2026-05-03 21:01:28 CST

- 改善 demo 後半段理解成本，避免 seller 掛售與 buyer 發需求後，觀眾不知道接下來發生什麼。
- 在 buyer 操作區新增 `What happened after the buyer clicked?` 摘要卡，直接列出 seller matched、seller executed、buyer verified、payment released 四個結果。
- 在 seller 操作區新增掛售後摘要，說明 seller listing 會進入供給市場、等待 buyer RFQ、被媒合後消耗 quota。
- 半螢幕 demo 驗證通過：點擊 buyer 後不用捲到下方，也能看到媒合、執行、驗證、付款的完整說明。

## 2026-05-03 16:32:25 CST

- 改善 demo 表單欄位可理解性，避免 demo 操作者不知道要填什麼。
- 將 buyer 欄位改為 `Work to buy`、`Market pair`、`Max buyer budget`，並加入 demo-safe helper text，清楚說明預設 ETH/USDC 任務會觸發 Coinbase-backed seller worker。
- 將 seller 欄位改為 `Seller agent name`、`Work this seller can do`、`How much idle quota to sell`、`Minimum price per task`，並加入每欄填寫提示。
- 將原本需要手打的 `market_data,api_call` capabilities 改成下拉選單，避免暴露內部 enum 給 demo 操作者。

## 2026-05-03 15:35:13 CST

- 修正半螢幕 demo 時點擊 buyer / seller 操作後看起來沒有反應的問題。
- 在 `demo/market-trace.html` 的左側操作區加入可見狀態卡，讓 buyer 發 RFQ 後立即顯示 matching / execution / verified 狀態，seller 掛售後立即顯示 listing 成功。
- 讓 buyer / seller submit button 在請求進行中改變文案並 disable，避免 demo 時重複點擊或誤以為沒有觸發。
- 驗證半螢幕 viewport 下，buyer 點擊後可看到 `Matched ... and verified delivery`，seller 點擊後可看到 `... is now listed`。

## 2026-05-03 15:18:11 CST

- 補上 seller supply/listing 流程：`scripts/serve_trade_playback.py` 現在維護本機 in-memory seller listings，包含能力、可用 quota、最低價格、信心分數、聲譽與預估延遲。
- 新增 `/api/listings`，讓 seller view 可以先掛售多餘 capacity；buyer RFQ 會從目前掛售的 sellers 中依照能力、budget、reputation 與 score 做媒合。
- 更新 `demo/market-trace.html`，支援 Buyer view / Seller view；seller 可以在一個瀏覽器掛售，buyer 可以在另一個瀏覽器發需求並看到 seller capacity board、bid book、matched seller 與 quota 消耗。
- 更新 demo 文件，建議用兩個瀏覽器分別開 `?role=seller` 與 `?role=buyer`，呈現「seller 先掛售、buyer 後採購、媒合後通知 seller 做事」的完整 marketplace flow。

## 2026-05-03 14:51:47 CST

- 新增 `agents/lib/market_data_task.py`，把 seller 的任務執行改成真實查詢 Coinbase Exchange 公開 ticker，而不是回傳固定假資料。
- 將 `agents/seller_agent.py` 與 `scripts/run_axl_demo.py` 接到同一個 seller worker；AXL demo 現在會在 seller 收到 locked trigger 後實際查市場資料、產生 delivery payload，並由 buyer 驗證 content hash。
- 將 `scripts/serve_trade_playback.py` 的 RFQ POST 改成 service-backed 真實 seller execution；成功時顯示 `coinbase_exchange` payload，失敗時明確標示 seller failed、hash not verified、payment blocked。
- 更新 `demo/market-trace.html`、`demo/README.md`、`README.md`，把 demo 說法修正為「service mode 會真實執行 seller market-data task；static file mode 才是 playback」。
- 新增 `tests/test_market_data_task.py`，測試 pair 正規化、Coinbase product mapping、delivery hash 穩定性、成功解析與失敗路徑。

## 2026-05-03 14:29:53 CST

- 依照 demo 方向調整，將 `demo/market-trace.html` 重做成產品式 Agent Bazaar trade room，而不是簡報式 guided story。
- 新版 demo page 以 Buyer agent、Active deal room、Seller bid book、Settlement、Agent event log、Proof references 組成，讓評審看起來像正在操作一個 agent 任務市場。
- 修正互動送出後的呈現邏輯，讓自訂 RFQ 仍維持完整 `settled` 交易狀態與正確 quote 數，不再出現交易已完成但顯示 `0 quotes` / `collecting` 的矛盾。
- 更新 `demo/README.md`，改以 trade room 作為主 demo surface，並將 terminal AXL demo 定位為輔助證據。

## 2026-05-03 13:50:40 CST

- 重做 demo page 的呈現方向，從偏流程說明的畫面調整成更像真實產品的 marketplace console。
- 將主視覺整理為 Buyer RFQ、Live deal room、Settlement proof 三個核心區塊，讓錄影時看起來像正在操作一個 agent market。
- 新增 Seller bid market、Agent event log、Proof references 區塊，用來同時呈現競價、AXL lifecycle、Base Sepolia / KeeperHub / Uniswap / ERC-8004 證據。
- 修正自訂 RFQ 送出後顯示 `0 quotes` / `collecting` 但交易已完成的矛盾狀態，改為使用後端回傳 trace 的 quote 數與 settled 狀態。
