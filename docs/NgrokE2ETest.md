# ngrok E2E 測試（人工）

在 24 小時電腦與手機上做。不要在沒有 ngrok URL 時假裝通過。

資料必須最後仍在：

```text
D:\出勤打卡系統\data\attendance.sqlite3
```

不要刪除、清空或改跑 PostgreSQL migration。

## 步驟

1. 24 小時電腦啟動 FastAPI：`scripts\start_production_pc.bat`（已設定 `CORS_ORIGINS`）或開發驗證用 `scripts\start_production.bat`。
2. 確認本機 `http://127.0.0.1:8800/health` 回 `status=ok`。
3. `scripts\start_ngrok.bat`。
4. 抄下 `https://....`（不要用 `http://`）。
5. 把該網址設成 GitHub Secret `ATTENDANCE_API_BASE`，重新部署 GitHub Pages。
6. 手機用 **4G/5G**（不要用公司 Wi-Fi 冒充外網）開啟  
   `https://<github-account>.github.io/attendance/`
7. Employee 登入。
8. `START`
9. `BREAK_START`
10. `BREAK_END`
11. `END`
12. 查詢今日出勤（工時不含休息）。
13. 補打卡（含超過 quota 仍可送出，並有警告）。
14. Admin 登入同一個 Pages 的 `/attendance/admin/`。
15. Admin 查詢、確認員工資料。
16. 閒置 3 分鐘：前端登出；之後用舊 token 呼叫 API 應為 401。

另外抽測（沿用既有規則，不改業務）：

- 無排班第一次 `START` 要填無排班原因
- `START` → `END` 要填未休息原因
- 早於排班結束的 `END` 要填提前下班原因
- Employee 呼叫 `/api/dashboard` 應為 403

## 通過條件

- 手機頁面打得到 ngrok API（瀏覽器 Network 沒有 CORS 錯誤）
- 上述打卡寫進同一份 SQLite
- `/docs` 在 `APP_ENV=production` 時不應公開
