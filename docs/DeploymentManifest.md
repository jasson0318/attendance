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
| `data\.gitkeep` | 確保 `data\` 目錄結構存在（**不含**正式資料） |

---

## 2. 不可複製

下列為開發產物或機敏／環境相依資料，**不要**從開發電腦帶進正式機：

| 路徑 | 原因 |
|------|------|
| **`data\attendance.sqlite3`** | **正式 SQLite，不可沿用開發庫**（正式機首次啟動自行初始化） |
| **`data\.secret_key`** | **正式 SECRET_KEY，不可沿用開發金鑰** |
| `__pycache__\` | Python 快取 |
| `.pytest_cache\` | 測試快取 |
| `.venv\` / `venv\` | 虛擬環境（應在正式機重裝套件） |
| `node_modules\` | 本專案不需要（若誤產生也不要複製） |
| `*.pyc` / `*.pid` / log / 暫存檔 | 執行產物 |
| 開發測試用附件／照片 | 非執行必要 |

---

## 3. 正式電腦第一次啟動時產生

| 路徑 | 說明 |
|------|------|
| `data\`（若不存在） | 啟動時建立 |
| `data\attendance.sqlite3` | create_all + migration + seed |
| `data\.secret_key` | 若未設 `ATTENDANCE_SECRET_KEY` 則自動建立並之後沿用 |

---

## 4. 正式電腦不能沿用開發電腦資料

特別標記：

| 檔案 | 規則 |
|------|------|
| `data\attendance.sqlite3` | **→ 不複製**；正式機獨立初始化 |
| `data\.secret_key` | **→ 不複製**；正式機獨立產生或設環境變數 |

若誤把開發機 SQLite／金鑰覆蓋到正式機：

- 可能混入測試打卡資料  
- JWT 簽章與開發機相同，不利隔離  

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
