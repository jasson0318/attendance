# 出勤打卡系統（Attendance System）

公司內部員工出勤管理與手機打卡系統（PWA / Mobile Web）。

## 環境需求

- Windows
- Python 3.12+

正式／雲端規劃：

- [docs/CloudMigration.md](docs/CloudMigration.md)
- [docs/EnvironmentVariables.md](docs/EnvironmentVariables.md)
- [docs/ProductionDeployment.md](docs/ProductionDeployment.md)
- [docs/DeploymentManifest.md](docs/DeploymentManifest.md)

開發電腦上的乾淨部署副本：`D:\出勤打卡系統_deploy`  
（以 `scripts\build_deploy_copy.bat` 產生；不含開發 SQLite／SECRET）

## 安裝

```bat
cd /d 專案目錄
scripts\install_requirements.bat
```

或：

```bat
python -m pip install -r requirements.txt
python scripts\generate_icons.py
```

## 啟動

開發／正式皆可：

```bat
scripts\start_production.bat
```

或：

```bat
python run.py
```

停止：

```bat
scripts\stop_production.bat
```

- 綁定：`0.0.0.0:8800`
- 本機：`http://127.0.0.1:8800`
- API 文件：`http://127.0.0.1:8800/docs`
- 管理後台：`http://127.0.0.1:8800/admin`

> 區網 IP（例如 `192.168.x.x:8800`）僅供同網段測試，**不是** 4 間門市的正式登入網址。  
> **正式門市手機要使用的網址，需要在 24 小時正式電腦完成外部連線設定後才能確定。**

## 預設帳號

| 角色 | 帳號 | 密碼 |
|------|------|------|
| 管理員 | admin | admin123 |
| 示範員工 | demo | demo123 |

請登入後立即修改密碼。

## 安全設定

JWT 簽章金鑰：

1. 環境變數 `ATTENDANCE_SECRET_KEY`（優先）
2. 否則自動使用／建立 `data\.secret_key`（已存在則不重建）

**不要**把真正密鑰寫進程式碼、前端或 Git。

## 資料庫

獨立 SQLite：`data\attendance.sqlite3`  
不與其他系統（含 SmartRx）共用。

## 測試

```bat
python -m pytest -q
python scripts\run_validation_checklist.py
```

## 功能摘要

- 員工帳號密碼登入後直接打卡（上班／開始休息／結束休息／下班）
- 嚴格打卡順序；跳過休息／提前下班／無排班需填原因
- 遲到／早退寬限；補打卡與超額警示
- Excel 排班匯入與報表匯出
- 管理員後台；3 分鐘無操作自動登出
- **無** GPS／Wi-Fi／QR／NFC／Beacon 現場驗證
