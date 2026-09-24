# 環境變數說明（Environment Variables）

機密放在 `.env` 或主機環境變數，**不要**寫進前端或 Git。

| 變數 | 必填 | 預設 | 說明 |
|------|------|------|------|
| `APP_ENV` | 正式必填 | `development` | `production` 時必須提供 `SECRET_KEY`。 |
| `DATABASE_URL` | 否 | 本機 SQLite | **目前正式庫就是預設 SQLite**。不要為了上線改成 PostgreSQL。 |
| `SECRET_KEY` | 正式必填 | （開發自動） | JWT 簽章。 |
| `ATTENDANCE_SECRET_KEY` | 否 | — | 同 `SECRET_KEY`（舊名）。 |
| `CORS_ORIGINS` | 正式建議設定 | `http://127.0.0.1:8800,http://localhost:8800` | 瀏覽器來源。正式改為 `https://<github-account>.github.io`。**禁止 `*`**。ngrok 網域不是頁面 Origin。 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 否 | `10080` | JWT `exp`。 |
| `IDLE_TIMEOUT_MINUTES` | 否 | `3` | 前後端閒置逾時。 |
| `APP_TIMEZONE` | 否 | `Asia/Taipei` | 業務時區。Windows 需要套件 `tzdata`（已列入 requirements.txt），否則 `ZoneInfo` 會失敗。 |
| `HOST` | 否 | `0.0.0.0` | bind。 |
| `PORT` | 否 | `8800` | 本機與 24 小時電腦用 8800。 |
| `PREVIEW_STORE` | 否 | `memory` | 目前單機用 `memory`。 |
| `ATTENDANCE_API_BASE` | Pages 正式 | （空） | GitHub Actions 寫入前端的 **ngrok HTTPS** 根網址。必須 `https://`。不要寫進 repo。 |

`POSTGRES_URL` 只給備用遷移工具。目前不要設定、不要執行 `--confirm`。


## 前端

- `frontend/static/js/config.js`：開發 `API_BASE=""`（同源 `http://127.0.0.1:8800`）
- Pages：`config.runtime.js` 由 GitHub Secret `ATTENDANCE_API_BASE` 產生，指向 ngrok `https://`。不可含 SECRET／DB。

## 安全

- `.env`、`*.sqlite3`、`.secret_key`、`logs/` 已在 `.gitignore`
- `/health`、`/api/public-config` 不回傳密鑰／連線字串
- 日誌禁止 password／SECRET／JWT
