/**
 * 登入 session：記住帳密（安全）+ 閒置自動登出（含右上角倒數）
 * 密碼絕不寫入 localStorage / sessionStorage / cookie。
 */
(function (global) {
  const TOKEN_KEY = "attendance_token";
  const REMEMBER_USER_KEY = "attendance_remember_user";
  const REMEMBER_FLAG_KEY = "attendance_remember_flag";
  const LOGOUT_MSG_KEY = "attendance_logout_msg";
  const LAST_ACTIVITY_KEY = "attendance_last_activity";

  function resolveIdleMs() {
    const mins =
      (global.AttendanceConfig && Number(global.AttendanceConfig.IDLE_TIMEOUT_MINUTES)) || 3;
    return Math.max(1, mins) * 60 * 1000;
  }

  let IDLE_MS = resolveIdleMs();
  const WARN_BEFORE_MS = 30 * 1000;

  /** 使用者活動（含手機觸控） */
  const ACTIVITY_EVENTS = [
    "pointerdown",
    "pointermove",
    "pointerup",
    "touchstart",
    "touchmove",
    "touchend",
    "mousedown",
    "mousemove",
    "mouseup",
    "click",
    "keydown",
    "keyup",
    "keypress",
    "input",
    "scroll",
    "wheel",
  ];

  function getToken() {
    return localStorage.getItem(TOKEN_KEY);
  }

  function setToken(t) {
    localStorage.setItem(TOKEN_KEY, t);
  }

  function clearToken() {
    localStorage.removeItem(TOKEN_KEY);
  }

  function setLogoutMessage(msg) {
    if (msg) sessionStorage.setItem(LOGOUT_MSG_KEY, msg);
    else sessionStorage.removeItem(LOGOUT_MSG_KEY);
  }

  function takeLogoutMessage() {
    const m = sessionStorage.getItem(LOGOUT_MSG_KEY);
    if (m) sessionStorage.removeItem(LOGOUT_MSG_KEY);
    return m;
  }

  function readStoredActivity() {
    try {
      const v = localStorage.getItem(LAST_ACTIVITY_KEY);
      if (!v) return null;
      const n = parseInt(v, 10);
      return Number.isFinite(n) ? n : null;
    } catch (_e) {
      return null;
    }
  }

  function writeStoredActivity(ts) {
    try {
      localStorage.setItem(LAST_ACTIVITY_KEY, String(ts));
    } catch (_e) {}
  }

  function clearStoredActivity() {
    try {
      localStorage.removeItem(LAST_ACTIVITY_KEY);
    } catch (_e) {}
  }

  function remainingMs(lastActivity, now) {
    return Math.max(0, IDLE_MS - Math.max(0, now - lastActivity));
  }

  function formatMmSs(ms) {
    var secs = Math.max(0, Math.ceil(Math.max(0, ms) / 1000));
    var m = Math.floor(secs / 60);
    var s = secs % 60;
    return String(m).padStart(2, "0") + ":" + String(s).padStart(2, "0");
  }

  /**
   * 記住帳密：僅保存帳號旗標；密碼交給 Credential Management / 瀏覽器密碼管理。
   */
  async function applyRemember(username, password, remember) {
    if (!remember) {
      localStorage.removeItem(REMEMBER_USER_KEY);
      localStorage.removeItem(REMEMBER_FLAG_KEY);
      return;
    }
    localStorage.setItem(REMEMBER_FLAG_KEY, "1");
    localStorage.setItem(REMEMBER_USER_KEY, username);
    try {
      if (global.PasswordCredential && navigator.credentials && navigator.credentials.store) {
        const cred = new PasswordCredential({
          id: username,
          name: username,
          password: password,
        });
        await navigator.credentials.store(cred);
      }
    } catch (_e) {}
  }

  async function fillRememberedFields(usernameEl, passwordEl, checkboxEl) {
    const flag = localStorage.getItem(REMEMBER_FLAG_KEY) === "1";
    const savedUser = localStorage.getItem(REMEMBER_USER_KEY) || "";
    if (checkboxEl) checkboxEl.checked = flag;
    if (flag && savedUser && usernameEl) usernameEl.value = savedUser;

    try {
      if (navigator.credentials && navigator.credentials.get) {
        const cred = await navigator.credentials.get({
          password: true,
          mediation: "optional",
        });
        if (cred && cred.id) {
          if (usernameEl) usernameEl.value = cred.id;
          if (passwordEl && cred.password) passwordEl.value = cred.password;
          if (checkboxEl) checkboxEl.checked = true;
        }
      }
    } catch (_e) {}
  }

  async function logoutSession(opts) {
    opts = opts || {};
    const t = getToken();
    clearToken();
    clearStoredActivity();
    if (opts.message) setLogoutMessage(opts.message);
    if (t) {
      try {
        const logoutUrl =
          (global.AttendanceConfig && AttendanceConfig.apiUrl)
            ? AttendanceConfig.apiUrl("/api/auth/logout")
            : "/api/auth/logout";
        await fetch(logoutUrl, {
          method: "POST",
          headers: { Authorization: "Bearer " + t },
        });
      } catch (_e) {}
    }
    if (opts.redirect !== false) {
      const home =
        (global.AttendanceConfig && AttendanceConfig.homeUrl)
          ? AttendanceConfig.homeUrl()
          : "/";
      global.location.replace(opts.href || home);
    }
  }

  function homeHref() {
    try {
      if (global.AttendanceConfig && AttendanceConfig.homeUrl) {
        return AttendanceConfig.homeUrl();
      }
    } catch (_e) {}
    return "/";
  }

  function protectHistory() {
    try {
      history.pushState({ attendance_guard: 1 }, "", location.href);
    } catch (_e) {}
    global.addEventListener("popstate", function () {
      if (!getToken()) {
        location.replace(homeHref());
        return;
      }
      try {
        history.pushState({ attendance_guard: 1 }, "", location.href);
      } catch (_e2) {}
    });
    global.addEventListener("pageshow", function (ev) {
      const path = location.pathname || "";
      const isHome =
        path === "/" ||
        path.endsWith("/attendance/") ||
        path.endsWith("/attendance") ||
        path.endsWith("index.html");
      if (!getToken() && !isHome) {
        location.replace(homeHref());
      }
      if (ev.persisted && !getToken()) {
        location.replace(homeHref());
      }
    });
  }

  function updateCountdownDom(remain, warning) {
    const el = document.getElementById("idle-countdown");
    if (!el) return;
    const timeEl = el.querySelector(".idle-countdown-time");
    const iconEl = el.querySelector(".idle-countdown-icon");
    const text = formatMmSs(remain);
    if (timeEl) timeEl.textContent = text;
    else el.textContent = (warning ? "⚠️ 自動登出 " : "🕒 自動登出 ") + text;
    if (iconEl) iconEl.textContent = warning ? "⚠️" : "🕒";
    el.classList.toggle("warn", !!warning);
    el.setAttribute("data-remaining", String(Math.ceil(remain / 1000)));
    el.hidden = false;
  }

  /**
   * 閒置監控：以 lastActivity + 3 分鐘計算剩餘；跨分頁／重新整理共用同一時間戳。
   * options.reset === true → 剛登入，重設為 03:00
   * options.reset === false → 沿用 localStorage 中的 lastActivity
   */
  function startIdleGuard(options) {
    options = options || {};
    const onWarn = options.onWarn || function () {};
    const onLogout = options.onLogout || function () {};
    const onContinueHide = options.onContinueHide || function () {};
    const onTick = options.onTick || function () {};
    const reset = !!options.reset;

    let lastActivity;
    let warnShown = false;
    let stopped = false;
    let timer = null;
    let lastPersist = 0;
    let lastServerPing = 0;
    const SERVER_PING_MS = 25000;
    const listeners = [];

    const now0 = Date.now();
    const stored = readStoredActivity();
    if (reset || stored == null) {
      lastActivity = now0;
      writeStoredActivity(lastActivity);
      lastPersist = lastActivity;
    } else if (now0 - stored >= IDLE_MS) {
      lastActivity = stored;
      // 已逾時：下一 tick 登出（先讓 UI 顯示 00:00）
    } else {
      lastActivity = stored;
    }

    function persist(ts, force) {
      if (force || ts - lastPersist >= 400) {
        writeStoredActivity(ts);
        lastPersist = ts;
      }
    }

    function pingServerActivity(force) {
      const token = getToken();
      if (!token) return;
      const now = Date.now();
      if (!force && now - lastServerPing < SERVER_PING_MS) return;
      lastServerPing = now;
      const url =
        global.AttendanceConfig && AttendanceConfig.apiUrl
          ? AttendanceConfig.apiUrl("/api/auth/activity")
          : "/api/auth/activity";
      try {
        fetch(url, {
          method: "POST",
          headers: { Authorization: "Bearer " + token },
          keepalive: true,
        }).catch(function () {});
      } catch (_e) {}
    }

    function bump(fromRemote) {
      if (stopped) return;
      lastActivity = Date.now();
      if (!fromRemote) {
        persist(lastActivity, false);
        pingServerActivity(false);
      }
      if (warnShown) {
        warnShown = false;
        onContinueHide();
      }
      paint();
    }

    function continueUse() {
      bump(false);
      persist(lastActivity, true);
      pingServerActivity(true);
    }

    function paint() {
      if (stopped) return;
      const now = Date.now();
      const remain = remainingMs(lastActivity, now);
      const warning = remain > 0 && remain <= WARN_BEFORE_MS;
      updateCountdownDom(remain, warning);
      onTick(remain, {
        warning: warning,
        display: formatMmSs(remain),
        lastActivity: lastActivity,
      });
    }

    function tick() {
      if (stopped) return;
      const now = Date.now();
      const remain = remainingMs(lastActivity, now);
      paint();
      if (remain <= 0) {
        stop();
        onLogout();
        return;
      }
      if (remain <= WARN_BEFORE_MS && !warnShown) {
        warnShown = true;
        onWarn();
      }
    }

    ACTIVITY_EVENTS.forEach(function (name) {
      const handler = function () {
        bump(false);
      };
      document.addEventListener(name, handler, { capture: true, passive: true });
      listeners.push({ name: name, handler: handler });
    });

    function onStorage(ev) {
      if (ev.key === TOKEN_KEY && !ev.newValue) {
        // 其他分頁已登出
        if (!stopped) {
          stop();
          location.replace(homeHref());
        }
        return;
      }
      if (ev.key !== LAST_ACTIVITY_KEY || !ev.newValue) return;
      const n = parseInt(ev.newValue, 10);
      if (!Number.isFinite(n)) return;
      lastActivity = n;
      if (warnShown) {
        warnShown = false;
        onContinueHide();
      }
      paint();
    }
    global.addEventListener("storage", onStorage);

    function onVisibility() {
      if (document.visibilityState === "visible") {
        persist(lastActivity, true);
        tick();
      }
    }
    document.addEventListener("visibilitychange", onVisibility);

    function onPageHide() {
      persist(lastActivity, true);
    }
    global.addEventListener("pagehide", onPageHide);

    timer = setInterval(tick, 250);
    paint();
    tick();
    // 登入後立即告知後端活動起點（與 login 寫入互補）
    if (reset) pingServerActivity(true);

    function stop() {
      stopped = true;
      if (timer) {
        clearInterval(timer);
        timer = null;
      }
      listeners.forEach(function (L) {
        document.removeEventListener(L.name, L.handler, { capture: true });
      });
      listeners.length = 0;
      global.removeEventListener("storage", onStorage);
      document.removeEventListener("visibilitychange", onVisibility);
      global.removeEventListener("pagehide", onPageHide);
    }

    return {
      bump: function () {
        bump(false);
      },
      continueUse: continueUse,
      stop: stop,
      getRemainingMs: function () {
        return remainingMs(lastActivity, Date.now());
      },
      getLastActivity: function () {
        return lastActivity;
      },
      IDLE_MS: IDLE_MS,
      WARN_BEFORE_MS: WARN_BEFORE_MS,
      ACTIVITY_EVENTS: ACTIVITY_EVENTS.slice(),
      LAST_ACTIVITY_KEY: LAST_ACTIVITY_KEY,
    };
  }

  function wireIdleUi(guard) {
    const modal = document.getElementById("idle-modal");
    const btn = document.getElementById("idle-continue");
    if (!modal || !btn) return;

    btn.onclick = function () {
      modal.classList.add("hidden");
      modal.setAttribute("aria-hidden", "true");
      guard.continueUse();
    };
  }

  function showIdleWarn() {
    const modal = document.getElementById("idle-modal");
    if (!modal) return;
    const text = modal.querySelector(".modal-text");
    if (text) text.textContent = "您已閒置，30秒後將自動登出。";
    modal.classList.remove("hidden");
    modal.setAttribute("aria-hidden", "false");
  }

  function hideIdleWarn() {
    const modal = document.getElementById("idle-modal");
    if (!modal) return;
    modal.classList.add("hidden");
    modal.setAttribute("aria-hidden", "true");
  }

  global.AttendanceAuth = {
    TOKEN_KEY: TOKEN_KEY,
    REMEMBER_USER_KEY: REMEMBER_USER_KEY,
    REMEMBER_FLAG_KEY: REMEMBER_FLAG_KEY,
    LAST_ACTIVITY_KEY: LAST_ACTIVITY_KEY,
    get IDLE_MS() {
      return IDLE_MS;
    },
    WARN_BEFORE_MS: WARN_BEFORE_MS,
    ACTIVITY_EVENTS: ACTIVITY_EVENTS,
    getToken: getToken,
    setToken: setToken,
    clearToken: clearToken,
    applyRemember: applyRemember,
    fillRememberedFields: fillRememberedFields,
    logoutSession: logoutSession,
    takeLogoutMessage: takeLogoutMessage,
    setLogoutMessage: setLogoutMessage,
    protectHistory: protectHistory,
    startIdleGuard: startIdleGuard,
    wireIdleUi: wireIdleUi,
    showIdleWarn: showIdleWarn,
    hideIdleWarn: hideIdleWarn,
    clearStoredActivity: clearStoredActivity,
    formatMmSs: formatMmSs,
    remainingMs: remainingMs,
    updateCountdownDom: updateCountdownDom,
    applyIdleTimeoutMinutes: function (mins) {
      IDLE_MS = Math.max(1, Number(mins) || 3) * 60 * 1000;
      if (global.AttendanceConfig) {
        global.AttendanceConfig.IDLE_TIMEOUT_MINUTES = Math.max(1, Number(mins) || 3);
      }
    },
  };
})(window);


