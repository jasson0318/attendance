# 環境變數說明（Environment Variables）

機密放在 `.env` 或主機環境變數，**不要**寫進前端或 Git。

| 變數 | 必填 | 預設 | 說明 |
|------|------|------|------|
| `APP_ENV` | 正式必填 | `development` | `production` 時必須提供 `SECRET_KEY`。 |
| `DATABASE_URL` | 否 | 本機 SQLite | 正式改 `postgresql+psycopg2://...` |
| `SECRET_KEY` | 正式必填 | （開發自動） | JWT 簽章。 |
| `ATTENDANCE_SECRET_KEY` | 否 | — | 同 `SECRET_KEY`（舊名）。 |
| `CORS_ORIGINS` | 否 | `http://127.0.0.1:8800,http://localhost:8800` | 逗號分隔；**禁止 `*`**。正式加 `https://<user>.github.io` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 否 | `10080` | JWT `exp`。 |
| `IDLE_TIMEOUT_MINUTES` | 否 | `3` | 前後端閒置逾時。 |
| `APP_TIMEZONE` | 否 | `Asia/Taipei` | 業務時區。 |
| `HOST` | 否 | `0.0.0.0` | bind。 |
| `PORT` | 否 | `8800` | Cloud 用平台 `$PORT`。 |
| `PREVIEW_STORE` | 否 | `memory` | `memory` 或 `postgres`（多實例 Excel 預覽）。 |
| `ATTENDANCE_API_BASE` | Pages 正式 | （空） | 僅 GitHub Actions／prepare 腳本寫入前端 `API_BASE`（非密鑰）。 |
| `POSTGRES_URL` | 遷移用 | — | `migrate_sqlite_to_postgres.py` 目標（可與 `DATABASE_URL` 相同）。 |

## 前端

- `frontend/static/js/config.js`：開發 `API_BASE=""`
- Pages：`config.runtime.js` 由 `prepare_github_pages.py` 產生（可含公網 API 根網址，**不可**含 SECRET／DB）

## 安全

- `.env`、`*.sqlite3`、`.secret_key`、`logs/` 已在 `.gitignore`
- `/health`、`/api/public-config` 不回傳密鑰／連線字串
- 日誌禁止 password／SECRET／JWT
