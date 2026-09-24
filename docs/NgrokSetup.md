# ngrok 安裝（24 小時電腦）

authtoken **只**存在 ngrok 自己的設定，不要寫進 `.bat`、原始碼或 Git。

## 1. 安裝 ngrok

到 ngrok 官網下載 Windows 版，並把 `ngrok.exe` 加入 PATH。  
本專案不內建 ngrok 二進位。

## 2. 登入

```bat
ngrok login
```

或到儀表板複製 authtoken 後：

```bat
ngrok config add-authtoken <你的 token>
```

這會寫入 ngrok 的使用者設定（通常是 `%LOCALAPPDATA%\ngrok\ngrok.yml`），不是這個專案。

## 3. 檢查

```bat
ngrok config check
```

## 4. 手動啟動（Free 測試）

先啟動 FastAPI，再：

```bat
cd /d D:\出勤打卡系統
scripts\start_ngrok.bat
```

等同：

```bat
ngrok http 127.0.0.1:8800
```

畫面上的 `Forwarding https://....` 就是之後要放進 `ATTENDANCE_API_BASE` 的值。

## 5. 固定網域（僅在你的方案已有保留網域時）

不要假造網域。若儀表板已有保留網域，可在 **ngrok 自己的設定**合併 `config\ngrok.endpoint.example.yml`，並依官方文件加上 `url`。不要把含 authtoken 的檔案放進 Git。

## 6. 開機自動啟動

確認手動啟動成功後，才在 24 小時電腦執行（需要你親自執行，本專案不會自動安裝）：

```bat
scripts\install_ngrok_service.bat INSTALL
```

移除：

```bat
scripts\uninstall_ngrok_service.bat UNINSTALL
```

`start_production_pc.bat` 需要事先設定：

```bat
set APP_ENV=production
set CORS_ORIGINS=https://<github-account>.github.io
```

`<github-account>` 請換成你的 GitHub 帳號，不要用 `*`。
