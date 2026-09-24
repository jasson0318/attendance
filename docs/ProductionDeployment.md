# 出勤打卡系統 — 正式部署說明

> **這份文件在開發電腦維護；實際安裝請到 24 小時正式電腦再執行【C】。**  
> **禁止修改 SmartRx。** 本系統獨立於 SmartRx。  
> **本階段不設定**外部連線（網域／Cloudflare／Tailscale／Port Forward／DDNS）。

---

## 【A 開發電腦】目前已完成

| 項目 | 狀態 |
|------|------|
| 帳號＋密碼登入後直接打卡 | 完成 |
| GPS／Wi-Fi／QR／NFC／Beacon | 未使用／已移除 |
| 測試 | 107 passed |
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

### C4. 建立正式 SECRET_KEY

- 優先：環境變數 `ATTENDANCE_SECRET_KEY`
- 否則：第一次啟動自動建立 `data\.secret_key`，之後沿用  
- **不要**使用開發電腦的 `.secret_key`

### C5. 初始化正式 SQLite

路徑：`data\attendance.sqlite3`  
第一次執行 FastAPI 會自動建表、migration、seed。  
**不要**覆蓋開發機的 SQLite。

預設帳號（請立刻改密）：

| 角色 | 帳號 | 密碼 |
|------|------|------|
| 管理員 | admin | admin123 |
| 示範員工 | demo | demo123 |

### C6. 啟動 FastAPI

```bat
scripts\start_production.bat
```

- 綁定：`0.0.0.0:8800`
- 本機確認：`http://127.0.0.1:8800`、`http://127.0.0.1:8800/api/health`

停止：

```bat
scripts\stop_production.bat
```

開機自動啟動：可用 Windows「工作排程器」在開機時執行 `scripts\start_production.bat`（細節見舊版說明段落或工作排程器 UI）。

---

## 【D 外部連線】目前不要設定

FastAPI 已支援 `0.0.0.0:8800`，但：

- **`192.168.x.x:8800` 只適用於同區網測試。**
- **4 間不同門市要正式使用，還需要另外建立「外部連線入口」。**
- **正式門市手機要使用的網址，需要在 24 小時正式電腦完成外部連線設定後才能確定。**

本文件**不**決定要用哪一種外部方案。請待之後另行指示。

因此：

> **目前還不能直接給 4 間門市手機使用，因為外部連線入口尚未設定。**

---

## 安全與架構約束（部署全程遵守）

- 不修改 SmartRx  
- 不加入 GPS／Wi-Fi／QR／NFC／Beacon  
- 不改既有打卡規則  
- SECRET_KEY 不寫進程式碼／前端／Git  
- 密碼維持 hash；3 分鐘無操作登出維持  
- 不自動改 Windows Firewall／路由器／Port Forward／DDNS／Cloudflare／Tailscale  
