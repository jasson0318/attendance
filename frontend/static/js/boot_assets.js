/**
 * 套用 BASE_PATH 到導覽連結（data-nav / data-page=admin|home）。
 * 不處理 Admin 側欄的 data-page 功能按鈕。
 */
(function () {
  function apply() {
    var cfg = window.AttendanceConfig;
    if (!cfg) return;
    document.querySelectorAll("a[data-nav='home'], a[data-page='home']").forEach(function (el) {
      if (cfg.homeUrl) el.setAttribute("href", cfg.homeUrl());
    });
    document.querySelectorAll("a[data-nav='admin'], a[data-page='admin']").forEach(function (el) {
      if (cfg.adminUrl) el.setAttribute("href", cfg.adminUrl());
    });
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", apply);
  } else {
    apply();
  }
})();
