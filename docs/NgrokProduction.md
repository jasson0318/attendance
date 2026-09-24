# ngrok 正式架構

目前正式架構（不是 Cloud PostgreSQL）：

```
員工 / Admin 瀏覽器
        ↓ HTTPS
GitHub Pages  /attendance/
        ↓ HTTPS + Bearer JWT
ngrok 公開 HTTPS
        ↓
24 小時 Windows 電腦  FastAPI  http://127.0.0.1:8800
        ↓
SQLite  data\attendance.sqlite3
```

同一套 Backend。不要再開第二套 API，也不要做 SQLite → PostgreSQL。

Alembic 與 `scripts/migrate_sqlite_to_postgres.py` 保留作未來備用，**不是**目前 production 的必要步驟。不要執行 `--confirm`。

## 流量

只允許 ngrok 轉到 FastAPI `:8800`。

ngrok **不要**暴露：

- SQLite 檔案
- Windows 檔案分享
- RDP
- 資料庫管理工具
- 其他 Windows 服務

## Free 與 Paid

| | Free（目前測試） | Paid / 固定網域 |
|--|--|--|
| 網址 | 重啟後常會換成新的 `*.ngrok-free.app` | 可使用保留網域，例如 `*.ngrok.app` |
| 用途 | 初期手機 4G/5G 測試 | 若需要固定網址、或要拿掉 free interstitial，再自行升級 |
| 程式 | 不假設方案 | 不假設方案 |

不要在程式裡寫死方案或網域。公開 API 根網址只放在 GitHub Secret `ATTENDANCE_API_BASE`。

本文件不購買任何方案。

## 網址變了要做什麼

Free 隨機網域在 ngrok 重啟後可能改變。

1. 看 ngrok 畫面上的 `https://....`
2. 更新 GitHub Secret `ATTENDANCE_API_BASE`（必須 `https://`，不含路徑）
3. 重新跑 GitHub Actions「Deploy GitHub Pages」

換網域不需要改 application code。

## 本機開發

開發電腦仍使用 `http://127.0.0.1:8800`，`API_BASE` 為空字串（同源 `/api`）。不要為了 ngrok 改掉本機開發。
