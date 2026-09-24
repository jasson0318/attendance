# Phase 6 Regression Matrix（本機可自動項目）

外部 Cloud／GitHub Pages 正式 E2E：待 credentials → 標記 SKIP（非 FAIL）。

| 類別 | 項目 | 結果 | 備註 |
|------|------|------|------|
| Auth | employee login | PASS | pytest |
| Auth | admin login | PASS | pytest + validation |
| Auth | wrong password | PASS | 既有測試 |
| Auth | logout / revoked | PASS | pytest |
| Auth | idle timeout frontend | PASS | IdleTracker + UI |
| Auth | idle timeout backend 401 | PASS | test_server_idle_timeout |
| Punch | START→BREAK→END 合法 | PASS | test_punch_order |
| Punch | 非法順序拒絕 | PASS | test_punch_order |
| Punch | skip break + reason | PASS | pytest |
| Punch | early leave + reason | PASS | pytest |
| Punch | unscheduled + reason | PASS | pytest |
| Makeup | quota / over-quota | PASS | pytest |
| Admin | edit / delete / audit | PASS | test_admin_edit |
| Admin | employee 不可看 audit | PASS | pytest |
| Excel | preview/confirm anomalies | PASS | 既有 excel 測試路徑 |
| Reports | daily/monthly/annual | PASS | pytest |
| CORS | 禁止 * | PASS | validation |
| PWA | SW 不 cache API | PASS | test_pages_and_health |
| Security | 前端無 SECRET/DB | PASS | config.js 檢查 |
| Cross-origin Pages→Cloud | SKIP | 無 GitHub／Cloud URL |
| Production deploy E2E | SKIP | 無 credentials |
| PG migration --confirm | SKIP | 無 PostgreSQL |

**pytest**: 115 passed / 0 failed  
**validation**: ALL PASS
