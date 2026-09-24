const TOKEN_KEY = (window.AttendanceAuth && AttendanceAuth.TOKEN_KEY) || "attendance_token";
const LABELS = {
  START: "上班打卡",
  BREAK_START: "開始休息",
  BREAK_END: "結束休息",
  END: "下班打卡",
};

let todayData = null;
let pendingPunch = null; // { eventType, extra }
let punching = false;
let idleGuard = null;

const CONFIRM_TEXT = {
  START: "確認要進行「上班打卡」嗎？",
  BREAK_START: "確認要進行「開始休息」嗎？",
  BREAK_END: "確認要進行「結束休息」嗎？",
  END: "確認要進行「下班打卡」嗎？",
};

function token() {
  return AttendanceAuth.getToken();
}
function setToken(t) {
  AttendanceAuth.setToken(t);
}
function clearToken() {
  AttendanceAuth.clearToken();
}

function nowClock() {
  const n = new Date();
  const p = (x) => String(x).padStart(2, "0");
  return `${p(n.getHours())}:${p(n.getMinutes())}:${p(n.getSeconds())}`;
}

function openConfirm(eventType, extra = {}) {
  pendingPunch = { eventType, extra };
  const needsNoBreak = !!extra._needs_no_break;
  const needsEarly = !!extra._needs_early;

  document.getElementById("confirm-text").textContent =
    CONFIRM_TEXT[eventType] || `確認要進行「${LABELS[eventType] || "打卡"}」嗎？`;
  document.getElementById("confirm-time").textContent = `現在時間：${nowClock()}`;

  const schedEl = document.getElementById("confirm-schedule");
  if (needsEarly && todayData && todayData.schedule && todayData.schedule.end) {
    schedEl.textContent = `排班下班：${todayData.schedule.end}`;
    schedEl.classList.remove("hidden");
  } else {
    schedEl.textContent = "";
    schedEl.classList.add("hidden");
  }

  const reasons = document.getElementById("confirm-reasons");
  const nbHint = document.getElementById("confirm-no-break-hint");
  const nbWrap = document.getElementById("confirm-no-break-wrap");
  const earlyWrap = document.getElementById("confirm-early-wrap");
  document.getElementById("confirm-no-break-reason").value = extra.no_break_reason || "";
  document.getElementById("confirm-early-reason").value = extra.early_leave_reason || "";

  if (needsNoBreak || needsEarly) {
    reasons.classList.remove("hidden");
    nbHint.classList.toggle("hidden", !needsNoBreak);
    nbWrap.classList.toggle("hidden", !needsNoBreak);
    earlyWrap.classList.toggle("hidden", !needsEarly);
    document.getElementById("confirm-ok").textContent =
      needsNoBreak && !needsEarly ? "確認下班" : "確認打卡";
  } else {
    reasons.classList.add("hidden");
    nbHint.classList.add("hidden");
    nbWrap.classList.add("hidden");
    earlyWrap.classList.add("hidden");
    document.getElementById("confirm-ok").textContent = "確認打卡";
  }

  const modal = document.getElementById("confirm-modal");
  modal.classList.remove("hidden");
  modal.setAttribute("aria-hidden", "false");
}

function closeConfirm() {
  pendingPunch = null;
  const modal = document.getElementById("confirm-modal");
  modal.classList.add("hidden");
  modal.setAttribute("aria-hidden", "true");
}

async function api(path, opts = {}) {
  const headers = opts.headers || {};
  if (!(opts.body instanceof FormData)) headers["Content-Type"] = "application/json";
  if (token()) headers["Authorization"] = `Bearer ${token()}`;
  headers["ngrok-skip-browser-warning"] = "1";
  const url = (window.AttendanceConfig && AttendanceConfig.apiUrl)
    ? AttendanceConfig.apiUrl(path)
    : path;
  const res = await fetch(url, { ...opts, headers });
  let data = null;
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) data = await res.json();
  else data = await res.text();
  if (res.status === 401 && path !== "/api/auth/login") {
    await AttendanceAuth.logoutSession({
      message: "登入已失效，請重新登入。",
      redirect: true,
    });
    throw new Error("未授權");
  }
  if (!res.ok) {
    const msg = (data && data.detail)
      ? (typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail))
      : res.statusText;
    throw new Error(msg);
  }
  return data;
}

function show(id) {
  document.getElementById("login-view").classList.toggle("hidden", id !== "login");
  document.getElementById("punch-view").classList.toggle("hidden", id !== "punch");
}

function stopIdle() {
  if (idleGuard) {
    idleGuard.stop();
    idleGuard = null;
  }
  AttendanceAuth.hideIdleWarn();
  const el = document.getElementById("idle-countdown");
  if (el) el.hidden = true;
}

function startIdle(opts) {
  stopIdle();
  const reset = !!(opts && opts.reset);
  idleGuard = AttendanceAuth.startIdleGuard({
    reset: reset,
    onWarn: () => AttendanceAuth.showIdleWarn(),
    onContinueHide: () => AttendanceAuth.hideIdleWarn(),
    onLogout: async () => {
      await AttendanceAuth.logoutSession({
        message: "您已閒置超過3分鐘，系統已自動登出。",
        redirect: true,
      });
    },
  });
  AttendanceAuth.wireIdleUi(idleGuard);
  AttendanceAuth.protectHistory();
}

async function login(e) {
  e.preventDefault();
  const err = document.getElementById("login-error");
  err.textContent = "";
  const username = document.getElementById("username").value.trim();
  const password = document.getElementById("password").value;
  const remember = document.getElementById("remember-credentials").checked;
  try {
    const data = await api("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    });
    await AttendanceAuth.applyRemember(username, password, remember);
    setToken(data.access_token);
    if (!remember) {
      document.getElementById("password").value = "";
    }
    await enterApp(data);
  } catch (ex) {
    err.textContent = ex.message;
  }
}

async function enterApp(loginData) {
  show("punch");
  // 剛登入重設 03:00；重新整理則沿用已存的 lastActivity
  try {
    const pub = await api("/api/public-config");
    if (pub && pub.idle_timeout_minutes && window.AttendanceAuth) {
      AttendanceAuth.applyIdleTimeoutMinutes(pub.idle_timeout_minutes);
    }
  } catch (_e) {}
  startIdle({ reset: !!loginData });
  const me = loginData || await api("/api/auth/me");
  document.getElementById("user-label").textContent =
    `${me.name}（${me.role === "admin" ? "管理員" : "員工"}）`;
  document.getElementById("admin-link").classList.toggle("hidden", me.role !== "admin");
  await loadToday();
}

async function doLogout() {
  stopIdle();
  await AttendanceAuth.logoutSession({ redirect: false });
  show("login");
  await AttendanceAuth.fillRememberedFields(
    document.getElementById("username"),
    document.getElementById("password"),
    document.getElementById("remember-credentials")
  );
}

function fillStoreSelect() {
  const sel = document.getElementById("unscheduled-store");
  sel.innerHTML = "";
  const stores = (todayData && todayData.stores) || [];
  const home = todayData && todayData.home_store_id;
  stores.forEach((s) => {
    const opt = document.createElement("option");
    opt.value = s.id;
    opt.textContent = s.name + (s.id === home ? "（所屬店舖）" : "");
    if (s.id === home) opt.selected = true;
    sel.appendChild(opt);
  });
}

function currentStatusText(data) {
  const ev = data.events || {};
  if (ev.END && ev.END.done) return "目前狀態：已下班";
  if (ev.BREAK_END && ev.BREAK_END.done) return "目前狀態：休息結束，可下班";
  if (ev.BREAK_START && ev.BREAK_START.done) return "目前狀態：休息中";
  if (ev.START && ev.START.done) return "目前狀態：已上班";
  if (data.needs_unscheduled_reason) return "目前狀態：無排班，上班打卡需填寫原因";
  return "目前狀態：尚未上班打卡";
}

function renderPunchButtons() {
  if (!todayData) return;
  const data = todayData;
  const grid = document.getElementById("punch-buttons");
  grid.innerHTML = "";
  const allowed = data.allowed || {};
  for (const [type, label] of Object.entries(LABELS)) {
    const ev = data.events[type];
    const btn = document.createElement("button");
    const isDone = !!ev.done;
    const isSkipped = !!ev.skipped;
    const orderOk = isDone ? false : allowed[type] !== false;
    btn.className = "btn punch" + (isDone || isSkipped ? " done" : "");
    btn.disabled = isDone ? true : !orderOk;
    if (isDone) {
      btn.textContent = `✓ ${label} ${ev.at || ""}`.trim();
    } else if (isSkipped) {
      btn.textContent = `未休息`;
      btn.disabled = true;
    } else {
      btn.textContent = label;
    }
    btn.onclick = () => onPunchClick(type);
    grid.appendChild(btn);
  }
}

async function loadToday() {
  let data;
  try {
    data = await api("/api/punch/today");
  } catch (ex) {
    console.error(ex);
    const box = document.getElementById("schedule-box");
    if (box) box.textContent = "今日出勤資料載入失敗，請重新整理或稍後再試。";
    const msg = document.getElementById("punch-msg");
    if (msg) {
      msg.textContent = "今日出勤資料載入失敗，請重新整理或稍後再試。";
      msg.className = "msg error";
    }
    return;
  }
  todayData = data;
  document.getElementById("today-date").textContent = data.date;
  const box = document.getElementById("schedule-box");
  const br = document.getElementById("break-box");
  const status = document.getElementById("status-box");
  if (!data.schedule) {
    box.textContent = "今日無排班（仍可打卡）";
    br.textContent = data.unscheduled
      ? `無排班出勤原因：${data.unscheduled.reason}`
      : "上班打卡時請填寫出勤原因";
  } else if (data.schedule.is_day_off) {
    box.textContent = "今日排班為休假（仍可臨時出勤打卡）";
    br.textContent = data.unscheduled
      ? `無排班出勤原因：${data.unscheduled.reason}`
      : "上班打卡時請填寫出勤原因";
  } else {
    box.textContent = `今日排班：${data.schedule.start}～${data.schedule.end}`;
    br.textContent = `休息：${data.schedule.break_start}～${data.schedule.break_end}`;
  }
  status.textContent = currentStatusText(data);
  const q = data.makeup.quota < 0 ? "不限" : data.makeup.quota;
  document.getElementById("makeup-quota").textContent =
    `本月補打卡已用 ${data.makeup.used} / ${q}（超過額度仍可補打，將列入考績）`;

  fillStoreSelect();
  renderPunchButtons();
}

function onPunchClick(eventType) {
  const msg = document.getElementById("punch-msg");
  if (!todayData) return;

  if (todayData.allowed && todayData.allowed[eventType] === false) {
    const orderHints = {
      BREAK_START: "請先完成上班打卡。",
      BREAK_END: "請先完成開始休息打卡。",
      END: todayData.events.BREAK_START && todayData.events.BREAK_START.done
        && !(todayData.events.BREAK_END && todayData.events.BREAK_END.done)
        ? "請先完成結束休息打卡。"
        : "請先完成上班打卡。",
    };
    msg.textContent = orderHints[eventType] || "目前無法進行此打卡。";
    msg.className = "msg error";
    return;
  }

  if (
    eventType === "START" &&
    todayData.needs_unscheduled_reason
  ) {
    document.getElementById("makeup-panel").classList.add("hidden");
    document.getElementById("unscheduled-panel").classList.remove("hidden");
    document.getElementById("unscheduled-reason").focus();
    return;
  }

  const extra = {};
  if (eventType === "END") {
    if (todayData.needs_no_break_reason) extra._needs_no_break = true;
    if (todayData.needs_early_leave_reason) extra._needs_early = true;
  }
  openConfirm(eventType, extra);
}

async function doPunch(eventType, extra = {}) {
  if (punching) return;
  punching = true;
  const msg = document.getElementById("punch-msg");
  msg.textContent = "打卡中…";
  msg.className = "msg";
  try {
    const payload = {
      event_type: eventType,
      is_makeup: false,
      ...extra,
    };
    delete payload._needs_no_break;
    delete payload._needs_early;
    const result = await api("/api/punch", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    msg.textContent = "打卡成功 " + (result.punched_at || "");
    msg.className = "msg ok";
    document.getElementById("unscheduled-panel").classList.add("hidden");
    await loadToday();
  } catch (ex) {
    msg.textContent = ex.message;
    msg.className = "msg error";
  } finally {
    punching = false;
  }
}

async function submitUnscheduledStart() {
  const reason = document.getElementById("unscheduled-reason").value.trim();
  const msg = document.getElementById("punch-msg");
  if (!reason) {
    msg.textContent = "今日沒有排班，請先填寫出勤原因。";
    msg.className = "msg error";
    return;
  }
  const punch_store_id = Number(document.getElementById("unscheduled-store").value);
  openConfirm("START", {
    unscheduled_reason: reason,
    punch_store_id,
  });
}

async function submitMakeup() {
  const msg = document.getElementById("punch-msg");
  const d = document.getElementById("makeup-date").value;
  const t = document.getElementById("makeup-time").value;
  const type = document.getElementById("makeup-type").value;
  const reason = document.getElementById("makeup-reason").value.trim();
  if (!d) {
    msg.textContent = "請選擇補打卡日期";
    msg.className = "msg error";
    return;
  }
  if (!reason) {
    msg.textContent = "請填寫補打卡原因。";
    msg.className = "msg error";
    return;
  }
  try {
    const body = {
      event_type: type,
      is_makeup: true,
      work_date: d,
      makeup_reason: reason,
      reason,
    };
    if (t) body.punched_at = `${d}T${t}:00`;
    const result = await api("/api/punch", {
      method: "POST",
      body: JSON.stringify(body),
    });
    if (result.warning) {
      msg.textContent = result.warning;
      msg.className = "msg warn";
    } else {
      msg.textContent = "補打卡成功";
      msg.className = "msg ok";
    }
    document.getElementById("makeup-reason").value = "";
    await loadToday();
  } catch (ex) {
    msg.textContent = ex.message;
    msg.className = "msg error";
  }
}

document.getElementById("login-form").addEventListener("submit", login);
document.getElementById("logout-btn").addEventListener("click", () => {
  doLogout();
});
document.getElementById("makeup-btn").addEventListener("click", () => {
  document.getElementById("unscheduled-panel").classList.add("hidden");
  const panel = document.getElementById("makeup-panel");
  panel.classList.toggle("hidden");
  if (!panel.classList.contains("hidden") && !document.getElementById("makeup-date").value) {
    const today = new Date();
    const y = today.getFullYear();
    const m = String(today.getMonth() + 1).padStart(2, "0");
    const d = String(today.getDate()).padStart(2, "0");
    document.getElementById("makeup-date").value = `${y}-${m}-${d}`;
  }
});
document.getElementById("makeup-submit").addEventListener("click", submitMakeup);
document.getElementById("unscheduled-submit").addEventListener("click", submitUnscheduledStart);
document.getElementById("unscheduled-cancel").addEventListener("click", () => {
  document.getElementById("unscheduled-panel").classList.add("hidden");
});
document.getElementById("confirm-cancel").addEventListener("click", closeConfirm);
document.getElementById("confirm-backdrop").addEventListener("click", closeConfirm);
document.getElementById("confirm-ok").addEventListener("click", async () => {
  if (!pendingPunch || punching) return;
  const { eventType, extra } = pendingPunch;
  const payload = { ...(extra || {}) };
  const msg = document.getElementById("punch-msg");

  if (payload._needs_no_break) {
    const r = document.getElementById("confirm-no-break-reason").value.trim();
    if (!r) {
      msg.textContent = "請填寫未休息原因。";
      msg.className = "msg error";
      return;
    }
    payload.no_break_reason = r;
  }
  if (payload._needs_early) {
    const r = document.getElementById("confirm-early-reason").value.trim();
    if (!r) {
      msg.textContent = "您目前尚未到排班下班時間，請說明提前下班原因。";
      msg.className = "msg error";
      return;
    }
    payload.early_leave_reason = r;
  }

  closeConfirm();
  await doPunch(eventType, payload);
  if (eventType === "START" && payload.unscheduled_reason) {
    document.getElementById("unscheduled-reason").value = "";
  }
});

if ("serviceWorker" in navigator) {
  const swUrl =
    (window.AttendanceConfig && AttendanceConfig.assetUrl)
      ? AttendanceConfig.assetUrl("/sw.js") + "?v=8"
      : "/sw.js?v=8";
  const swScope =
    (window.AttendanceConfig && AttendanceConfig.BASE_PATH)
      ? AttendanceConfig.BASE_PATH + "/"
      : "/";
  navigator.serviceWorker.register(swUrl, { scope: swScope }).then((reg) => {
    reg.update();
  }).catch(() => {});
  caches.keys().then((keys) => {
    keys.filter((k) => k !== "attendance-v8").forEach((k) => caches.delete(k));
  });
}

(async () => {
  const notice = AttendanceAuth.takeLogoutMessage();
  const noticeEl = document.getElementById("login-notice");
  if (notice && noticeEl) {
    noticeEl.textContent = notice;
    noticeEl.classList.remove("hidden");
  }
  await AttendanceAuth.fillRememberedFields(
    document.getElementById("username"),
    document.getElementById("password"),
    document.getElementById("remember-credentials")
  );
  if (!token()) {
    show("login");
    return;
  }
  try {
    await enterApp();
  } catch {
    clearToken();
    show("login");
  }
})();
