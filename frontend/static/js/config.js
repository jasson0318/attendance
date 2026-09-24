/**
 * 前端非機密設定（開發 + GitHub Pages）。
 *
 * API_BASE：
 *   - 開發（FastAPI 同源提供靜態頁）："" → 請求相對路徑 /api/...
 *   - GitHub Pages：由 GitHub Secret ATTENDANCE_API_BASE 注入
 *     （ngrok 公開 HTTPS，例如 https://<domain>）。勿在此寫死網域。
 *
 * BASE_PATH：
 *   - 本機 FastAPI："" （網址為 / 與 /admin）
 *   - GitHub Pages："/attendance"
 *
 * 切勿放置 SECRET_KEY、DATABASE_URL、密碼。
 */
(function (global) {
  var injected = global.ATTENDANCE_CONFIG || {};
  var cfg = global.AttendanceConfig || {};
  if (typeof cfg.API_BASE !== "string" && typeof injected.API_BASE === "string") {
    cfg.API_BASE = injected.API_BASE;
  }
  if (typeof cfg.BASE_PATH !== "string" && typeof injected.BASE_PATH === "string") {
    cfg.BASE_PATH = injected.BASE_PATH;
  }

  function detectBasePath() {
    if (typeof cfg.BASE_PATH === "string" && cfg.BASE_PATH.length) {
      return String(cfg.BASE_PATH).replace(/\/$/, "");
    }
    try {
      var path = global.location && global.location.pathname ? global.location.pathname : "";
      if (path === "/attendance" || path.indexOf("/attendance/") === 0) {
        return "/attendance";
      }
    } catch (_e) {}
    return "";
  }

  cfg.BASE_PATH = detectBasePath();

  // 開發預設空字串；Pages 正式 API 由部署準備腳本覆寫（勿在此寫死網域／埠號）
  if (typeof cfg.API_BASE !== "string") {
    cfg.API_BASE = "";
  }
  cfg.API_BASE = String(cfg.API_BASE).replace(/\/$/, "");

  if (!cfg.IDLE_TIMEOUT_MINUTES) {
    cfg.IDLE_TIMEOUT_MINUTES = 3;
  }

  cfg.assetUrl = function (path) {
    var p = path || "";
    if (p.charAt(0) !== "/") p = "/" + p;
    return (cfg.BASE_PATH || "") + p;
  };

  cfg.apiUrl = function (path) {
    var p = path || "";
    if (p.charAt(0) !== "/") p = "/" + p;
    // 有 API_BASE（GitHub Pages → ngrok HTTPS）時走絕對 API；否則同源相對 /api
    return (cfg.API_BASE || "") + p;
  };

  /** 員工端首頁 */
  cfg.homeUrl = function () {
    return cfg.BASE_PATH ? cfg.BASE_PATH + "/" : "/";
  };

  /**
   * 管理後台：
   * - 本機 FastAPI：/admin（既有路由）
   * - GitHub Pages：/attendance/admin/（亦相容 admin.html）
   */
  cfg.adminUrl = function () {
    if (cfg.BASE_PATH) {
      return cfg.BASE_PATH + "/admin/";
    }
    return "/admin";
  };

  global.AttendanceConfig = cfg;
})(window);
