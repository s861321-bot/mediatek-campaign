# 聯發科紅白對抗賽｜活動網頁＋管理後台

包含：前台手機版問卷、姓名電話、同電話防重複、001～060 連續發號、額滿提醒、管理員登入、搜尋、意向篩選、CSV 匯出、SQLite 資料儲存。

## 本機啟動

1. 安裝 Python 3.10+。
2. `pip install -r requirements.txt`
3. 設定環境變數 `SECRET_KEY`（長且隨機）、`ADMIN_PASSWORD`（至少12字元）、`DATABASE_PATH`（例如 `./campaign.sqlite3`）。本機 HTTP 測試時另設定 `COOKIE_SECURE=0`，正式 HTTPS 不可關閉。
4. 執行 `python app.py`，瀏覽 `http://localhost:8000`。
5. 後台 `http://localhost:8000/admin`，使用 `ADMIN_PASSWORD` 登入。

正式部署使用 `waitress-serve --listen=0.0.0.0:$PORT app:app` 或合適的 WSGI 服務。必須使用 HTTPS、持久化硬碟（SQLite 資料檔不能放在會重置的暫存檔案系統），並備份資料庫。若平台以多台機器分散部署，請改用共用 PostgreSQL 資料庫，而非各機器獨立 SQLite。

## 正式啟用注意事項

- 請填妥個資告知：主辦單位正式名稱、聯絡方法、活動規則、個資利用期間/地區/對象/方式、權利行使方式；需要廣告行銷同意時，應獨立取得。
- 前台尚未整合簡訊 OTP，現為「同電話不可重複填寫」，但無法阻止他人冒填號碼；必要時增加 OTP 與濫用防護。
- 管理密碼與 SECRET_KEY 必須透過主機環境變數設定，不可放進 HTML、Git 或分享文件。
- 為公開正式活動，還應配置登入限速、IP 濫用限制、備份、存取記錄與備援，並經安全檢測。
- CSV 中電話以 Excel 文字格式輸出，以保留開頭的 0。
- 本專案包含網站程式，不代表已經上線；需要部署到伺服器才能供不同手機即時共用序號。
