const TOKEN_KEY = (window.AttendanceAuth && AttendanceAuth.TOKEN_KEY) || "attendance_token";
const TITLES = {
  dashboard: "Dashboard",
  employees: "員工管理",
  stores: "店舖管理",
  schedules: "排班管理",
  excel: "Excel匯入",
  today: "今日出勤",
  query: "出勤查詢",
  makeup: "補打卡紀錄",
  audit: "操作紀錄",
  reports: "報表",
  settings: "系統設定",
};

let idleGuard = null;

function token() {
  return AttendanceAuth.getToken();
}

async function api(path, opts = {}) {
  const headers = opts.headers || {};
  if (!(opts.body instanceof FormData)) {
    if (opts.body && !headers["Content-Type"]) headers["Content-Type"] = "application/json";
  }
  if (token()) headers["Authorization"] = `Bearer ${token()}`;
  const url = (window.AttendanceConfig && AttendanceConfig.apiUrl)
    ? AttendanceConfig.apiUrl(path)
    : path;
  const res = await fetch(url, { ...opts, headers });
  if (res.status === 401 || res.status === 403) {
    await AttendanceAuth.logoutSession({
      message: res.status === 401 ? "登入已失效，請重新登入。" : "請以管理員登入",
      redirect: true,
    });
    throw new Error("unauthorized");
  }
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) {
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || JSON.stringify(data));
    return data;
  }
  if (!res.ok) throw new Error(await res.text());
  return res;
}

function startIdle(opts) {
  if (idleGuard) idleGuard.stop();
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

const page = document.getElementById("page");

async function renderDashboard() {
  const d = await api("/api/dashboard");
  page.innerHTML = `
    <div class="stats">
      <div class="stat"><div class="n">${d.active_employees}</div><div class="l">在職員工</div></div>
      <div class="stat"><div class="n">${d.stores}</div><div class="l">店舖</div></div>
      <div class="stat"><div class="n">${d.scheduled_today}</div><div class="l">今日排班</div></div>
      <div class="stat"><div class="n">${d.punched_start_today}</div><div class="l">已上班打卡</div></div>
      <div class="stat"><div class="n">${d.absent_today}</div><div class="l">今日曠職</div></div>
      <div class="stat"><div class="n">${d.makeup_this_month}</div><div class="l">本月補打卡</div></div>
      <div class="stat"><div class="n">${d.makeup_over_quota_this_month}</div><div class="l">超額補打卡</div></div>
    </div>
    <div class="panel" style="margin-top:16px">
      <h3>各店概況</h3>
      <table><thead><tr><th>店舖</th><th>員工</th><th>今日排班</th></tr></thead>
      <tbody>${d.by_store.map(s => `<tr><td>${s.store}</td><td>${s.employees}</td><td>${s.scheduled_today}</td></tr>`).join("")}</tbody></table>
    </div>`;
}

function empFormHtml(stores, e = null) {
  const isEdit = !!e;
  return `
    <div class="panel" id="emp-editor">
      <h3>${isEdit ? "編輯員工" : "新增員工"}</h3>
      <div class="form-grid">
        <label>姓名<input id="e-name" value="${e ? e.name : ""}"></label>
        <label>排班代碼<input id="e-code" value="${e ? e.schedule_code : ""}"></label>
        <label>店舖<select id="e-store">${stores.map(s =>
          `<option value="${s.id}" ${e && e.store_id === s.id ? "selected" : ""}>${s.name}</option>`
        ).join("")}</select></label>
        <label>帳號<input id="e-user" value="${e ? e.username : ""}"></label>
        ${isEdit ? "" : '<label>密碼<input id="e-pass" type="password"></label>'}
        <label>到職日<input id="e-hire" type="date" value="${e && e.hire_date ? e.hire_date : ""}"></label>
        <label>離職日<input id="e-leave" type="date" value="${e && e.leave_date ? e.leave_date : ""}"></label>
        <label>約定工時<input id="e-hours" type="number" step="0.5" value="${e ? e.agreed_daily_hours : 8}"></label>
        <label>休息開始<input id="e-bs" type="time" value="${e && e.break_start ? String(e.break_start).slice(0,5) : "12:00"}"></label>
        <label>休息結束<input id="e-be" type="time" value="${e && e.break_end ? String(e.break_end).slice(0,5) : "13:00"}"></label>
        <label>狀態<select id="e-active">
          <option value="true" ${!e || e.is_active ? "selected" : ""}>在職</option>
          <option value="false" ${e && !e.is_active ? "selected" : ""}>停用</option>
        </select></label>
      </div>
      <div class="toolbar">
        <button class="btn-sm" id="e-save">${isEdit ? "儲存修改" : "新增"}</button>
        ${isEdit ? '<button class="btn-sm light" id="e-cancel">取消編輯</button>' : ""}
      </div>
    </div>`;
}

function readEmpForm() {
  return {
    name: document.getElementById("e-name").value.trim(),
    schedule_code: document.getElementById("e-code").value.trim(),
    store_id: Number(document.getElementById("e-store").value),
    username: document.getElementById("e-user").value.trim(),
    hire_date: document.getElementById("e-hire").value || null,
    leave_date: document.getElementById("e-leave").value || null,
    agreed_daily_hours: Number(document.getElementById("e-hours").value || 8),
    break_start: document.getElementById("e-bs").value || null,
    break_end: document.getElementById("e-be").value || null,
    is_active: document.getElementById("e-active").value === "true",
  };
}

async function renderEmployees(editId = null) {
  const stores = await api("/api/stores");
  const list = await api("/api/employees");
  const editing = editId ? list.find(x => x.id === editId) : null;
  page.innerHTML = `
    ${empFormHtml(stores, editing)}
    <div class="panel">
      <table>
        <thead><tr><th>姓名</th><th>代碼</th><th>店舖</th><th>帳號</th><th>在職</th><th>操作</th></tr></thead>
        <tbody id="emp-tbody"></tbody>
      </table>
    </div>`;
  const tbody = document.getElementById("emp-tbody");
  tbody.innerHTML = list.filter(e => e.role !== "admin" || true).map(e => {
    const store = stores.find(s => s.id === e.store_id);
    return `<tr>
      <td>${e.name}</td><td>${e.schedule_code}</td><td>${store ? store.name : e.store_id}</td>
      <td>${e.username}</td><td>${e.is_active ? "是" : "否"}</td>
      <td>
        <button class="btn-sm light" data-edit="${e.id}">編輯</button>
        <button class="btn-sm light" data-reset="${e.id}">重設密碼</button>
        <button class="btn-sm light" data-toggle="${e.id}" data-active="${e.is_active}">${e.is_active ? "停用" : "啟用"}</button>
      </td>
    </tr>`;
  }).join("");

  document.getElementById("e-save").onclick = async () => {
    const body = readEmpForm();
    if (!body.name || !body.schedule_code || !body.username) {
      alert("請填寫姓名、排班代碼、帳號");
      return;
    }
    if (editing) {
      await api(`/api/employees/${editing.id}`, { method: "PUT", body: JSON.stringify(body) });
    } else {
      const pass = document.getElementById("e-pass")?.value;
      if (!pass) { alert("請填寫密碼"); return; }
      await api("/api/employees", {
        method: "POST",
        body: JSON.stringify({ ...body, password: pass }),
      });
    }
    renderEmployees();
  };
  const cancel = document.getElementById("e-cancel");
  if (cancel) cancel.onclick = () => renderEmployees();

  tbody.querySelectorAll("[data-edit]").forEach(btn => {
    btn.onclick = () => renderEmployees(Number(btn.dataset.edit));
  });
  tbody.querySelectorAll("[data-reset]").forEach(btn => {
    btn.onclick = async () => {
      const pw = prompt("新密碼");
      if (!pw) return;
      await api(`/api/employees/${btn.dataset.reset}/reset-password`, {
        method: "POST",
        body: JSON.stringify({ password: pw }),
      });
      alert("已重設");
    };
  });
  tbody.querySelectorAll("[data-toggle]").forEach(btn => {
    btn.onclick = async () => {
      const active = btn.dataset.active === "true";
      await api(`/api/employees/${btn.dataset.toggle}`, {
        method: "PUT",
        body: JSON.stringify({ is_active: !active }),
      });
      renderEmployees();
    };
  });
}

async function renderToday() {
  const today = new Date().toISOString().slice(0, 10);
  page.innerHTML = `
    <div class="panel">
      <div class="toolbar">
        <label>日期<input id="t-date" type="date" value="${today}"></label>
        <button class="btn-sm" id="t-load">重新整理</button>
      </div>
      <div id="t-list" style="overflow:auto"></div>
    </div>
    <div id="t-detail"></div>`;

  async function loadList() {
    const d = document.getElementById("t-date").value;
    const rows = await api(`/api/admin/attendance/today?work_date=${d}`);
    document.getElementById("t-list").innerHTML = `<table>
      <thead><tr>
        <th>員工</th><th>上班</th><th>休息開始</th><th>休息結束</th><th>下班</th>
        <th>遲到</th><th>早退</th><th>狀態</th><th>操作</th>
      </tr></thead>
      <tbody>${rows.map(r => `<tr>
        <td>${r.employee_name}</td>
        <td>${r.actual_start || "-"}</td>
        <td>${r.actual_break_start || "-"}</td>
        <td>${r.actual_break_end || "-"}</td>
        <td>${r.actual_end || "-"}</td>
        <td>${r.late_minutes}</td>
        <td>${r.early_leave_minutes}</td>
        <td>${r.attendance_status_label || ""}</td>
        <td><button class="btn-sm light" data-manage="${r.employee_id}" data-date="${r.work_date}">管理</button></td>
      </tr>`).join("") || "<tr><td colspan='9'>尚無出勤資料（可先為員工排班或打卡）</td></tr>"}</tbody>
    </table>`;
    document.querySelectorAll("[data-manage]").forEach(btn => {
      btn.onclick = () => openDayDetail(Number(btn.dataset.manage), btn.dataset.date);
    });
  }

  async function openDayDetail(employeeId, workDate) {
    const detail = await api(`/api/admin/attendance/day-detail?employee_id=${employeeId}&work_date=${workDate}`);
    const box = document.getElementById("t-detail");
    box.innerHTML = `
      <div class="panel">
        <h3>${detail.employee_name}　${detail.work_date}　出勤管理</h3>
        <p class="muted">狀態：${detail.attendance_status_label || ""}　
          遲到 ${detail.late_minutes} 分　早退 ${detail.early_leave_minutes} 分　
          工作 ${detail.work_minutes} 分　跨度 ${detail.span_minutes} 分</p>
        <div id="event-rows"></div>
        <div class="toolbar" style="margin-top:16px">
          <button class="btn-sm" id="del-all" style="background:#c1121f">全部刪除當日打卡</button>
          <button class="btn-sm light" id="close-detail">關閉</button>
        </div>
        <h4 style="margin-top:20px">操作歷史（僅管理員可見）</h4>
        <div id="audit-day" style="overflow:auto"></div>
      </div>`;
    const rows = document.getElementById("event-rows");
    rows.innerHTML = detail.events.map(ev => `
      <div class="form-grid" style="margin-bottom:10px;align-items:end;border-bottom:1px solid #e5eef0;padding-bottom:10px">
        <div><b>${ev.event_label}</b><div class="muted">${ev.display_time || "尚未打卡"}${ev.is_makeup ? "（補打）" : ""}</div></div>
        <label>時間
          <input type="datetime-local" data-dt="${ev.event_type}"
            value="${ev.punched_at ? ev.punched_at.slice(0,16) : workDate + "T08:00"}">
        </label>
        <div>
          <button class="btn-sm light" data-save-ev="${ev.event_type}">編輯／儲存</button>
          ${ev.exists ? `<button class="btn-sm light" data-del-ev="${ev.id}" data-label="${ev.event_label}">刪除</button>` : ""}
        </div>
      </div>`).join("");

    rows.querySelectorAll("[data-save-ev]").forEach(btn => {
      btn.onclick = async () => {
        const type = btn.dataset.saveEv;
        const inp = rows.querySelector(`[data-dt="${type}"]`);
        if (!inp.value) return alert("請輸入時間");
        const punched_at = inp.value.length === 16 ? inp.value + ":00" : inp.value;
        const reason = prompt("操作原因（可留空）") || "";
        await api("/api/admin/attendance/events", {
          method: "PUT",
          body: JSON.stringify({
            employee_id: employeeId,
            work_date: workDate,
            event_type: type,
            punched_at,
            reason,
          }),
        });
        openDayDetail(employeeId, workDate);
        loadList();
      };
    });
    rows.querySelectorAll("[data-del-ev]").forEach(btn => {
      btn.onclick = async () => {
        if (!confirm(`確定要刪除這筆「${btn.dataset.label}」打卡嗎？`)) return;
        const reason = prompt("刪除原因（可留空）") || "";
        await api(`/api/admin/attendance/events/${btn.dataset.delEv}?reason=${encodeURIComponent(reason)}`, {
          method: "DELETE",
        });
        openDayDetail(employeeId, workDate);
        loadList();
      };
    });
    document.getElementById("del-all").onclick = async () => {
      if (!confirm(`確定要刪除 ${detail.employee_name} ${workDate} 的全部打卡紀錄嗎？`)) return;
      const reason = prompt("全部刪除原因（可留空）") || "";
      await api("/api/admin/attendance/day-delete", {
        method: "POST",
        body: JSON.stringify({ employee_id: employeeId, work_date: workDate, reason }),
      });
      openDayDetail(employeeId, workDate);
      loadList();
    };
    document.getElementById("close-detail").onclick = () => { box.innerHTML = ""; };

    const audits = await api(
      `/api/admin/attendance/audit-logs?employee_id=${employeeId}&work_date=${workDate}&limit=50`
    );
    document.getElementById("audit-day").innerHTML = audits.length
      ? `<table><thead><tr>
          <th>時間</th><th>管理員</th><th>操作</th><th>事件</th><th>原始</th><th>修改後</th><th>原因</th>
        </tr></thead><tbody>${audits.map(a => `<tr>
          <td>${(a.created_at || "").replace("T", " ")}</td>
          <td>${a.admin_name || a.admin_username || ""}</td>
          <td>${a.action_label || a.action}</td>
          <td>${a.event_label || a.event_type || a.deleted || ""}</td>
          <td>${a.original_time || "-"}</td>
          <td>${a.new_time || "-"}</td>
          <td>${a.reason || ""}</td>
        </tr>`).join("")}</tbody></table>`
      : "<p class='muted'>尚無操作歷史</p>";
  }

  document.getElementById("t-load").onclick = loadList;
  document.getElementById("t-date").onchange = loadList;
  loadList();
}

async function renderStores() {
  const stores = await api("/api/stores");
  page.innerHTML = `<div class="panel"><table>
    <thead><tr><th>名稱</th><th>代碼</th><th>啟用</th><th></th></tr></thead>
    <tbody>${stores.map(s => `
      <tr data-id="${s.id}">
        <td><input value="${s.name}" data-f="name"></td>
        <td class="muted">${s.code}</td>
        <td>
          <select data-f="is_active">
            <option value="true" ${s.is_active ? "selected" : ""}>是</option>
            <option value="false" ${!s.is_active ? "selected" : ""}>否</option>
          </select>
        </td>
        <td><button class="btn-sm save">儲存</button></td>
      </tr>`).join("")}</tbody></table></div>`;
  page.querySelectorAll(".save").forEach(btn => {
    btn.onclick = async () => {
      const tr = btn.closest("tr");
      const body = {};
      tr.querySelectorAll("[data-f]").forEach(inp => {
        let v = inp.value;
        const f = inp.dataset.f;
        if (f === "is_active") v = v === "true";
        body[f] = v;
      });
      await api(`/api/stores/${tr.dataset.id}`, { method: "PUT", body: JSON.stringify(body) });
      alert("已儲存");
    };
  });
}

async function renderSchedules() {
  const stores = await api("/api/stores");
  const emps = await api("/api/employees");
  const now = new Date();
  page.innerHTML = `
    <div class="panel">
      <div class="toolbar">
        <label>店舖<select id="sch-store"><option value="">全部</option>${stores.map(s=>`<option value="${s.id}">${s.name}</option>`).join("")}</select></label>
        <label>年<input id="sch-y" type="number" value="${now.getFullYear()}"></label>
        <label>月<input id="sch-m" type="number" value="${now.getMonth()+1}"></label>
        <button class="btn-sm" id="sch-load">查詢</button>
      </div>
      <div class="form-grid">
        <label>員工<select id="sch-emp">${emps.filter(e=>e.role==='employee').map(e=>`<option value="${e.id}">${e.name}（${e.schedule_code}）</option>`).join("")}</select></label>
        <label>日期<input id="sch-date" type="date"></label>
        <label>上班<input id="sch-s" type="time" value="08:00"></label>
        <label>休息起<input id="sch-bs" type="time" value="12:00"></label>
        <label>休息迄<input id="sch-be" type="time" value="13:00"></label>
        <label>下班<input id="sch-e" type="time" value="17:00"></label>
      </div>
      <button class="btn-sm" id="sch-add">新增排班</button>
      <button class="btn-sm light" id="sch-off">設為休假</button>
      <div id="sch-table" style="margin-top:12px"></div>
    </div>`;
  async function load() {
    const y = Number(document.getElementById("sch-y").value);
    const m = Number(document.getElementById("sch-m").value);
    const store_id = document.getElementById("sch-store").value;
    let url = `/api/schedules?year=${y}&month=${m}`;
    if (store_id) url += `&store_id=${store_id}`;
    const rows = await api(url);
    document.getElementById("sch-table").innerHTML = `<table><thead><tr><th>日期</th><th>員工ID</th><th>班次</th><th>休息</th><th>休假</th></tr></thead>
      <tbody>${rows.map(r=>`<tr><td>${r.work_date}</td><td>${r.employee_id}</td><td>${r.start_time||''}～${r.end_time||''}</td><td>${r.break_start||''}～${r.break_end||''}</td><td>${r.is_day_off?'是':'否'}</td></tr>`).join("")}</tbody></table>`;
  }
  document.getElementById("sch-load").onclick = load;
  document.getElementById("sch-add").onclick = async () => {
    const empId = Number(document.getElementById("sch-emp").value);
    const emp = emps.find(e => e.id === empId);
    await api("/api/schedules", {
      method: "POST",
      body: JSON.stringify({
        employee_id: empId,
        store_id: emp.store_id,
        work_date: document.getElementById("sch-date").value,
        start_time: document.getElementById("sch-s").value,
        break_start: document.getElementById("sch-bs").value,
        break_end: document.getElementById("sch-be").value,
        end_time: document.getElementById("sch-e").value,
        is_day_off: false,
      }),
    });
    load();
  };
  document.getElementById("sch-off").onclick = async () => {
    await api("/api/schedules/day-off", {
      method: "POST",
      body: JSON.stringify({
        employee_id: Number(document.getElementById("sch-emp").value),
        work_date: document.getElementById("sch-date").value,
        is_day_off: true,
      }),
    });
    load();
  };
  load();
}

async function renderExcel() {
  const stores = await api("/api/stores");
  const now = new Date();
  page.innerHTML = `
    <div class="panel">
      <p>上傳公司現有月曆式 Excel 排班表。流程：解析 → 預覽 → 檢查異常 → 確認匯入。</p>
      <div class="toolbar">
        <label>店舖<select id="x-store">${stores.map(s=>`<option value="${s.id}">${s.name}</option>`).join("")}</select></label>
        <label>年<input id="x-y" type="number" value="${now.getFullYear()}"></label>
        <label>月<input id="x-m" type="number" value="${now.getMonth()+1}"></label>
        <label>檔案<input id="x-file" type="file" accept=".xlsx,.xls"></label>
        <button class="btn-sm" id="x-preview">預覽</button>
        <button class="btn-sm" id="x-confirm">確認匯入</button>
      </div>
      <div id="x-result"></div>
    </div>`;
  document.getElementById("x-preview").onclick = async () => {
    const file = document.getElementById("x-file").files[0];
    if (!file) return alert("請選擇檔案");
    const fd = new FormData();
    fd.append("file", file);
    fd.append("store_id", document.getElementById("x-store").value);
    fd.append("year", document.getElementById("x-y").value);
    fd.append("month", document.getElementById("x-m").value);
    const data = await api("/api/excel/import/preview", { method: "POST", body: fd });
    document.getElementById("x-result").innerHTML = `
      <p>可匯入 <b class="ok">${data.ok_count}</b> 筆，異常 <b class="issue-err">${data.error_count}</b> 筆</p>
      <h4>異常</h4>
      <ul>${data.issues.map(i=>`<li class="issue-err">[${i.code}] ${i.message}</li>`).join("") || "<li>無</li>"}</ul>
      <h4>預覽（前 50）</h4>
      <table><thead><tr><th>代碼</th><th>員工</th><th>日期</th><th>班次</th><th>OK</th></tr></thead>
      <tbody>${data.rows.slice(0,50).map(r=>`<tr><td>${r.schedule_code}</td><td>${r.employee_name||''}</td><td>${r.work_date}</td><td>${r.is_day_off?'休':`${r.start}～${r.end}`}</td><td>${r.ok?'✓':'✗'}</td></tr>`).join("")}</tbody></table>`;
  };
  document.getElementById("x-confirm").onclick = async () => {
    const fd = new FormData();
    fd.append("store_id", document.getElementById("x-store").value);
    fd.append("year", document.getElementById("x-y").value);
    fd.append("month", document.getElementById("x-m").value);
    const data = await api("/api/excel/import/confirm", { method: "POST", body: fd });
    alert(data.message);
  };
}

async function renderQuery() {
  const stores = await api("/api/stores");
  const emps = await api("/api/employees");
  page.innerHTML = `
    <div class="panel">
      <div class="toolbar">
        <label>月份<input id="q-month" type="month"></label>
        <label>店舖<select id="q-store"><option value="">全部</option>${stores.map(s=>`<option value="${s.id}">${s.name}</option>`).join("")}</select></label>
        <label>員工<select id="q-emp"><option value="">全部</option>${emps.map(e=>`<option value="${e.id}">${e.name}</option>`).join("")}</select></label>
        <button class="btn-sm" id="q-go">查詢</button>
      </div>
      <div id="q-out" style="overflow:auto"></div>
    </div>`;
  document.getElementById("q-go").onclick = async () => {
    const month = document.getElementById("q-month").value;
    const store_id = document.getElementById("q-store").value;
    const employee_id = document.getElementById("q-emp").value;
    let url = "/api/attendance/query?";
    if (month) url += `month=${month}&`;
    if (store_id) url += `store_id=${store_id}&`;
    if (employee_id) url += `employee_id=${employee_id}&`;
    const rows = await api(url);
    document.getElementById("q-out").innerHTML = `<table><thead><tr>
      <th>日期</th><th>員工</th><th>店</th><th>排班</th><th>出勤狀態</th>
      <th>休息</th><th>狀態說明</th><th>未休息原因</th><th>提前下班原因</th>
      <th>排班上班</th><th>實際上班</th><th>排班休起</th><th>實際休起</th>
      <th>排班休迄</th><th>實際休迄</th><th>排班下班</th><th>實際下班</th>
      <th>休息分</th><th>工作</th><th>跨度</th><th>遲到</th><th>早退</th><th>補打</th><th>曠職</th>
    </tr></thead><tbody>${rows.map(r=>{
      const breakLabel = r.no_break_reason
        ? "未休息"
        : ((r.actual_break_start || "") + (r.actual_break_end ? "～" + r.actual_break_end : "") || "-");
      const statusNote = r.no_break_reason
        ? "未休息"
        : (r.early_leave_reason ? "提前下班" : (r.unscheduled_reason ? "無排班" : "-"));
      return `<tr>
      <td>${r.work_date}</td><td>${r.employee_name}</td><td>${r.store_name}</td>
      <td>${r.has_schedule ? "有" : "無"}</td>
      <td>${r.attendance_status_label || r.attendance_status || ""}</td>
      <td>${breakLabel}</td>
      <td>${statusNote}</td>
      <td>${r.no_break_reason || "-"}</td>
      <td>${r.early_leave_reason || "-"}</td>
      <td>${r.scheduled_start||''}</td><td>${r.actual_start||''}</td>
      <td>${r.scheduled_break_start||''}</td><td>${r.actual_break_start||''}</td>
      <td>${r.scheduled_break_end||''}</td><td>${r.actual_break_end||''}</td>
      <td>${r.scheduled_end||''}</td><td>${r.actual_end||''}</td>
      <td>${r.break_minutes}</td><td>${r.work_minutes}</td><td>${r.span_minutes}</td>
      <td>${r.late_minutes}</td><td>${r.early_leave_minutes}</td><td>${r.makeup_count}</td>
      <td>${r.is_absent?'是':'否'}</td>
    </tr>`;
    }).join("")}</tbody></table>`;
  };
}

async function renderMakeup() {
  const rows = await api("/api/attendance/makeup");
  page.innerHTML = `<div class="panel"><table>
    <thead><tr>
      <th>日期</th><th>員工</th><th>店舖</th><th>項目</th>
      <th>補打時間</th><th>提交時間</th><th>原因</th>
      <th>本月次數</th><th>超額</th>
    </tr></thead>
    <tbody>${rows.map(r => `<tr>
      <td>${r.work_date}</td>
      <td>${r.employee_name}</td>
      <td>${r.store_name || ""}</td>
      <td>${r.event_label || r.event_type}</td>
      <td>${r.punched_at ? r.punched_at.replace("T", " ").slice(0, 16) : ""}</td>
      <td>${r.submitted_at ? r.submitted_at.replace("T", " ").slice(0, 16) : (r.created_at || "")}</td>
      <td>${r.reason || ""}</td>
      <td>${r.sequence_in_month}</td>
      <td>${r.over_quota ? "是" : "否"}</td>
    </tr>`).join("")}</tbody></table></div>`;
}

async function renderReports() {
  const now = new Date();
  page.innerHTML = `
    <div class="panel">
      <h3>匯出 Excel</h3>
      <div class="toolbar">
        <label>日期<input id="r-date" type="date" value="${now.toISOString().slice(0,10)}"></label>
        <button class="btn-sm" id="r-daily">每日出勤</button>
      </div>
      <div class="toolbar">
        <label>年<input id="r-y" type="number" value="${now.getFullYear()}"></label>
        <label>月<input id="r-m" type="number" value="${now.getMonth()+1}"></label>
        <button class="btn-sm" id="r-month">月報</button>
        <button class="btn-sm" id="r-year">年度報表</button>
      </div>
      <div id="r-annual"></div>
    </div>`;
  const dl = async (url, name) => {
    const full = (window.AttendanceConfig && AttendanceConfig.apiUrl)
      ? AttendanceConfig.apiUrl(url)
      : url;
    const res = await fetch(full, { headers: { Authorization: `Bearer ${token()}` } });
    if (!res.ok) return alert("匯出失敗");
    const blob = await res.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = name;
    a.click();
  };
  document.getElementById("r-daily").onclick = () => {
    const d = document.getElementById("r-date").value;
    dl(`/api/excel/export/daily?work_date=${d}`, `daily_${d}.xlsx`);
  };
  document.getElementById("r-month").onclick = () => {
    const y = document.getElementById("r-y").value;
    const m = document.getElementById("r-m").value;
    dl(`/api/excel/export/monthly?year=${y}&month=${m}`, `monthly_${y}_${m}.xlsx`);
  };
  document.getElementById("r-year").onclick = async () => {
    const y = document.getElementById("r-y").value;
    const rows = await api(`/api/attendance/annual?year=${y}`);
    document.getElementById("r-annual").innerHTML = `<table><thead><tr>
      <th>員工</th><th>店舖</th><th>約定時數</th><th>實際出勤</th><th>打卡跨度</th><th>曠職</th>
      <th>遲到次數</th><th>遲到時數</th><th>早退次數</th><th>早退時數</th>
      <th>未休息次數</th><th>提前下班次數</th>
      <th>補打</th><th>超額補打</th><th>無排班出勤次數</th><th>無排班出勤時數</th>
    </tr></thead><tbody>${rows.map(r=>`<tr>
      <td>${r.employee}</td><td>${r.store}</td><td>${r.agreed_work_hours}</td><td>${r.actual_work_hours}</td>
      <td>${r.actual_span_hours}</td><td>${r.absent_hours}</td><td>${r.late_count}</td><td>${r.late_hours}</td>
      <td>${r.early_leave_count}</td><td>${r.early_leave_hours}</td>
      <td>${r.no_break_count ?? 0}</td><td>${r.early_leave_reason_count ?? 0}</td>
      <td>${r.makeup_total}</td><td>${r.makeup_over_quota}</td>
      <td>${r.unscheduled_count}</td><td>${r.unscheduled_hours}</td>
    </tr>`).join("")}</tbody></table>`;
    dl(`/api/excel/export/annual?year=${y}`, `annual_${y}.xlsx`);
  };
}

async function renderSettings() {
  const s = await api("/api/settings");
  page.innerHTML = `
    <div class="panel">
      <div class="form-grid">
        <label>遲到寬限
          <select id="s-late">${[0,5,10,15].map(v=>`<option value="${v}" ${s.late_grace_minutes===v?'selected':''}>${v}分鐘</option>`).join("")}</select>
        </label>
        <label>早退寬限
          <select id="s-early">${[0,5,10,15].map(v=>`<option value="${v}" ${s.early_leave_grace_minutes===v?'selected':''}>${v}分鐘</option>`).join("")}</select>
        </label>
        <label>遲到縮短休息補回
          <select id="s-comp"><option value="true" ${s.late_break_compensation?'selected':''}>啟用</option><option value="false" ${!s.late_break_compensation?'selected':''}>停用</option></select>
        </label>
        <label>月補打卡額度
          <select id="s-quota">${[3,5,7,-1].map(v=>`<option value="${v}" ${s.monthly_makeup_quota===v?'selected':''}>${v<0?'不限':v+'次'}</option>`).join("")}</select>
        </label>
      </div>
      <p class="muted">打卡僅需帳號密碼登入，不再使用 GPS／Wi-Fi／QR 等現場驗證。</p>
      <button class="btn-sm" id="s-save">儲存設定</button>
    </div>`;
  document.getElementById("s-save").onclick = async () => {
    await api("/api/settings", {
      method: "PUT",
      body: JSON.stringify({
        late_grace_minutes: Number(document.getElementById("s-late").value),
        early_leave_grace_minutes: Number(document.getElementById("s-early").value),
        late_break_compensation: document.getElementById("s-comp").value === "true",
        monthly_makeup_quota: Number(document.getElementById("s-quota").value),
      }),
    });
    alert("已儲存");
  };
}

async function renderAudit() {
  const emps = await api("/api/employees");
  page.innerHTML = `
    <div class="panel">
      <div class="toolbar">
        <label>員工<select id="a-emp"><option value="">全部</option>
          ${emps.map(e => `<option value="${e.id}">${e.name}</option>`).join("")}
        </select></label>
        <label>日期<input id="a-date" type="date"></label>
        <button class="btn-sm" id="a-go">查詢</button>
      </div>
      <p class="muted">操作歷史僅管理員可見；員工端不會顯示任何修改／刪除紀錄。</p>
      <div id="a-out" style="overflow:auto"></div>
    </div>`;
  document.getElementById("a-go").onclick = async () => {
    let url = "/api/admin/attendance/audit-logs?limit=200";
    const emp = document.getElementById("a-emp").value;
    const d = document.getElementById("a-date").value;
    if (emp) url += `&employee_id=${emp}`;
    if (d) url += `&work_date=${d}`;
    const rows = await api(url);
    document.getElementById("a-out").innerHTML = `<table>
      <thead><tr>
        <th>操作時間</th><th>管理員</th><th>員工</th><th>日期</th>
        <th>操作</th><th>事件</th><th>原始時間</th><th>修改後</th><th>原因</th>
      </tr></thead>
      <tbody>${rows.map(a => `<tr>
        <td>${(a.created_at || "").replace("T", " ")}</td>
        <td>${a.admin_name || ""}</td>
        <td>${a.employee_name || ""}</td>
        <td>${a.work_date || ""}</td>
        <td>${a.action_label || a.action}</td>
        <td>${a.event_label || a.event_type || a.deleted || ""}</td>
        <td>${a.original_time || "-"}</td>
        <td>${a.new_time || "-"}</td>
        <td>${a.reason || ""}</td>
      </tr>`).join("")}</tbody></table>`;
  };
  document.getElementById("a-go").click();
}

const RENDERERS = {
  dashboard: renderDashboard,
  employees: renderEmployees,
  stores: renderStores,
  schedules: renderSchedules,
  excel: renderExcel,
  today: renderToday,
  query: renderQuery,
  makeup: renderMakeup,
  audit: renderAudit,
  reports: renderReports,
  settings: renderSettings,
};

document.querySelectorAll("#nav button").forEach(btn => {
  btn.onclick = () => {
    document.querySelectorAll("#nav button").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    const p = btn.dataset.page;
    document.getElementById("page-title").textContent = TITLES[p];
    RENDERERS[p]().catch(e => { page.innerHTML = `<p class="issue-err">${e.message}</p>`; });
  };
});

function goHome() {
  const url =
    (window.AttendanceConfig && AttendanceConfig.homeUrl)
      ? AttendanceConfig.homeUrl()
      : "/";
  location.href = url;
}

(async () => {
  if (!token()) { goHome(); return; }
  try {
    try {
      const pub = await api("/api/public-config");
      if (pub && pub.idle_timeout_minutes && window.AttendanceAuth) {
        AttendanceAuth.applyIdleTimeoutMinutes(pub.idle_timeout_minutes);
      }
    } catch (_e) {}
    const me = await api("/api/auth/me");
    if (me.role !== "admin") { alert("需要管理員"); goHome(); return; }
    document.getElementById("admin-user").textContent = me.name;
    // 從打卡頁進入後台：沿用同一閒置計時，勿重設
    startIdle({ reset: false });
    await renderDashboard();
  } catch {
    goHome();
  }
})();
