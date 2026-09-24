# 出勤打卡系統 — 正式部署說明

> **這份文件在開發電腦維護；實際安裝請到 24 小時正式電腦再執行【C】。**  
> **禁止修改 SmartRx。** 本系統獨立於 SmartRx。  
> **對外連線只用 ngrok → FastAPI :8800。** 不要 Port Forward／Cloudflare Tunnel／Tailscale／VPN／DDNS。

---

## 【A 開發電腦】目前已完成

| 項目 | 狀態 |
|------|------|
| 帳號＋密碼登入後直接打卡 | 完成 |
| GPS／Wi-Fi／QR／NFC／Beacon | 未使用／已移除 |
| 測試 | 見 pytest / validation 報告 |
| Validation | ALL PASS |
| 正式啟動腳本 | `scripts\start_production.bat` 等 |
| 部署副本 | `D:\出勤打卡系統_deploy` |

開發專案（請保留）：

```text
D:\出勤打卡系統
```

部署副本（可搬運）：

```text
D:\出勤打卡系統_deploy
```

開發電腦驗證：

```bat
cd /d D:\出勤打卡系統
python -m pytest -q
python scripts\run_validation_checklist.py
scripts\preflight_check.bat
```

區網如 `http://192.168.x.x:8800` **僅同區網測試**，不是門市正式入口。

詳見：`docs\DeploymentManifest.md`

---

## 【B 複製到 24 小時正式電腦】

將開發電腦上的部署副本整個複製過去，例如：

```text
來源（開發電腦）:  D:\出勤打卡系統_deploy
目標（正式電腦）:  D:\出勤打卡系統
```

可用 USB、共用資料夾、壓縮後傳輸等任何方式（本階段不打包強制 ZIP）。

**必須帶走：** `backend`、`frontend`、`scripts`、`docs`、`requirements.txt`、`run.py`、`README.md`、`pytest.ini`、`.gitignore`、`data\.gitkeep`

**不可帶走：**

| 檔案 | 規則 |
|------|------|
| `data\attendance.sqlite3` | **不複製** |
| `data\.secret_key` | **不複製** |
| `__pycache__`、`.pytest_cache`、`.venv` | **不複製** |

---

## 【C 正式電腦】（稍後再操作；此處僅說明）

### C1. 安裝 Python

安裝 **Python 3.12+**，勾選 **Add python.exe to PATH**。

### C2. 安裝套件

```bat
cd /d D:\出勤打卡系統
scripts\install_requirements.bat
```

### C3. 部署前檢查

```bat
scripts\preflight_check.bat
```

只回報問題，**不會**改防火牆／網路／自動裝 Python。

### C4. SECRET_KEY

- 優先：環境變數 `SECRET_KEY` 或 `ATTENDANCE_SECRET_KEY`
- 否則：若 `data\.secret_key` 已存在就沿用；沒有才自動建立
- **不要**把金鑰寫進 Git

### C5. SQLite（正式資料庫）

路徑：`data\attendance.sqlite3`  
這份檔案就是正式資料。不要刪除、不要清空、不要覆蓋成空庫，不要執行 PostgreSQL migration。

### C6. 啟動 FastAPI

24 小時電腦（需已設定 `CORS_ORIGINS`）：

```bat
scripts\start_production_pc.bat
```

本機開發驗證：

```bat
scripts\start_production.bat
```

- 綁定：`0.0.0.0:8800`
- 本機確認：`http://127.0.0.1:8800`、`http://127.0.0.1:8800/health`

停止：

```bat
scripts\stop_production.bat
```

開機自動啟動（要你親自執行，不會自動安裝）：

```bat
scripts\install_ngrok_service.bat INSTALL
```

---

## 【D 外部連線】ngrok（目前正式方案）

手機不直接開 `http://127.0.0.1:8800`。

```
GitHub Pages  --HTTPS-->  ngrok  --tunnel-->  127.0.0.1:8800  -->  SQLite
```

- 不要 Port Forward、VPN、Cloudflare Tunnel、Tailscale、DDNS。
- 不要把區網 IP 當成門市正式網址。
- 安裝與開機啟動見 `docs/NgrokSetup.md`。
- **不要刪除或重建** `data\attendance.sqlite3`。它就是正式資料庫。
- **不要**執行 PostgreSQL migration。

### C5 更正

若 `data\attendance.sqlite3` 已存在，啟動時沿用，不要覆蓋、不要清空。  
第一次在空目錄啟動才會建表；那不是把現有正式庫換掉。

---

## 安全與架構約束（部署全程遵守）

- 不修改 SmartRx  
- 不加入 GPS／Wi-Fi／QR／NFC／Beacon  
- 不改既有打卡規則  
- SECRET_KEY 不寫進程式碼／前端／Git  
- 密碼維持 hash；3 分鐘無操作登出維持  
- 不自動改 Windows Firewall／路由器／Port Forward／DDNS／Cloudflare／Tailscale  
