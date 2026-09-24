# 部署檔案清單（Deployment Manifest）

對照來源與部署副本：

| 項目 | 路徑 |
|------|------|
| 開發專案（保留不動） | `D:\出勤打卡系統` |
| 部署副本（可搬到正式機） | `D:\出勤打卡系統_deploy` |

---

## 1. 必須複製

搬到 24 小時正式電腦時，請包含下列項目（部署副本已整理好）：

| 路徑 | 說明 |
|------|------|
| `backend\` | FastAPI 後端、models、routers、services、migration、seed、tests |
| `frontend\` | 員工／管理前端、靜態資源、PWA |
| `scripts\` | 安裝／啟動／停止／preflight |
| `docs\` | 部署說明與本清單 |
| `requirements.txt` | Python 套件 |
| `run.py` | 正式啟動入口 |
| `pytest.ini` | 測試設定（正式機可選，建議一併帶走驗證） |
| `README.md` | 專案說明 |
| `.gitignore` | 避免之後誤提交敏感檔 |
| `data\.gitkeep` | 確保 `data\` 目錄結構存在 |
| `data\attendance.sqlite3` | **正式資料庫。複製到 24 小時電腦時保留，不要進 Git** |

---

## 2. 不要覆蓋正式資料庫

`data\attendance.sqlite3` **就是目前正式資料**。  
搬到 24 小時電腦時要帶上這份檔案，不要刪除、不要清空、不要用空庫覆蓋。

不要放進 Git。

| 路徑 | 原因 |
|------|------|
| `__pycache__\` | Python 快取 |
| `.pytest_cache\` | 測試快取 |
| `.venv\` / `venv\` | 虛擬環境（在正式機重裝套件） |
| `ngrok.yml` / authtoken | 只放在 ngrok 自己的設定 |
| `.env` | 機密 |

`data\.secret_key` 不要提交 Git。若 24 小時電腦是新機器且未複製此檔，第一次啟動會產生新的 JWT 金鑰；既有帳號密碼仍在 SQLite 裡，員工重新登入即可。

## 3. 不要做的事

- 不要執行 `migrate_sqlite_to_postgres.py --confirm`
- 不要把 Cloud PostgreSQL 當成目前正式庫
- 對外只開 ngrok → `127.0.0.1:8800`，見 `docs\NgrokProduction.md`

---

## 5. 部署副本建立方式（開發電腦）

在開發電腦已產生：

```text
D:\出勤打卡系統_deploy
```

此目錄為乾淨副本，可直接整個資料夾複製到正式電腦後改名為例如：

```text
D:\出勤打卡系統
```

然後依 `docs\ProductionDeployment.md` 的【C 正式電腦】步驟安裝與啟動。
