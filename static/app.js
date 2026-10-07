const $ = s => document.querySelector(s);
const api = async (url, method = "GET", body) => {
  const r = await fetch(url, { method, headers: { "Content-Type": "application/json" }, body: body && JSON.stringify(body) });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(d.error || "Something went wrong.");
  return d;
};
const toast = m => { const t = $("#toast"); t.textContent = m; t.classList.add("show"); setTimeout(() => t.classList.remove("show"), 2600); };
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const pill = p => `<span class="pill ${p.low ? "low" : "good"}">${p.percentage}%</span>`;
const bar = p => `<div class="bar ${p.low ? "low" : ""}"><i style="width:${Math.min(p.percentage, 100)}%"></i></div>`;
let me, tab;

const PAGES = {
  dashboard: ["Dashboard", async v => {
    const d = await api("/api/dashboard");
    v.innerHTML = `<h1>Dashboard</h1><div class="stats">
      <div class="stat"><b>${d.total}</b><span>Total students</span></div>
      <div class="stat"><b>${d.present}</b><span>Present today</span></div>
      <div class="stat"><b>${d.absent}</b><span>Absent today</span></div>
      <div class="stat"><b>${d.on_leave}</b><span>On leave</span></div>
      <div class="stat"><b>${d.average}%</b><span>Average attendance</span></div>
      <div class="stat alert"><b>${d.low.length}</b><span>Low attendance (below ${d.threshold}%)</span></div></div>
      <h3>Students with low attendance</h3>${lowTable(d.low)}`;
  }],
  students: ["Students", async v => {
    const admin = me.role === "admin";
    v.innerHTML = `<h1>Students</h1>
      <div class="panel row"><label>Search by name or roll no<input id="sq"></label></div>
      ${admin ? `<div class="panel"><b>Add student</b><div class="row">
        <label>Roll no<input id="nr"></label><label>Name<input id="nn"></label><label>Email<input id="ne"></label>
        <label>Department<input id="nd"></label><label>Fingerprint ID<input id="nf" placeholder="e.g. FP006"></label>
        <button id="add" class="primary" style="margin:0">Add student</button></div></div>` : ""}
      <div class="panel" id="list"></div><div id="detail"></div>`;
    const load = async () => {
      const rows = await api("/api/students?q=" + encodeURIComponent($("#sq").value));
      $("#list").innerHTML = rows.length ? `<table><tr><th>Roll no</th><th>Name</th><th>Dept</th><th>Fingerprint</th><th>Attendance</th><th>Status</th><th></th></tr>` +
        rows.map(s => `<tr><td>${esc(s.roll_no)}</td><td>${esc(s.name)}</td><td>${esc(s.department)}</td><td>${esc(s.fingerprint_id)}</td>
        <td>${pill(s)}</td><td>${s.active ? "Active" : "Inactive"}</td><td>
        <button class="sm" data-v="${s.id}">View</button>
        ${admin ? `<button class="sm" data-e="${s.id}">Edit</button>${s.active ? `<button class="sm danger" data-d="${s.id}">Deactivate</button>` : ""}` : ""}</td></tr>`).join("") + "</table>"
        : `<p class="muted">No students match your search.</p>`;
      $("#list").onclick = async e => {
        const b = e.target.closest("button"); if (!b) return;
        try {
          if (b.dataset.v) showDetail(b.dataset.v);
          if (b.dataset.d && confirm("Deactivate this student? Their attendance history is kept.")) { await api("/api/students/" + b.dataset.d, "DELETE"); toast("Student deactivated"); load(); }
          if (b.dataset.e) {
            const s = rows.find(x => x.id == b.dataset.e);
            const name = prompt("Name", s.name); if (name === null) return;
            const dept = prompt("Department", s.department || ""); if (dept === null) return;
            const email = prompt("Email", s.email || ""); if (email === null) return;
            const fp = prompt("Fingerprint ID", s.fingerprint_id || ""); if (fp === null) return;
            await api("/api/students/" + s.id, "PUT", { name, department: dept, email, fingerprint_id: fp, active: 1 }); toast("Student updated"); load();
          }
        } catch (er) { toast(er.message); }
      };
    };
    $("#sq").oninput = load;
    if (admin) $("#add").onclick = async () => {
      try { await api("/api/students", "POST", { roll_no: $("#nr").value.trim(), name: $("#nn").value.trim(), email: $("#ne").value, department: $("#nd").value, fingerprint_id: $("#nf").value.trim() });
        toast("Student added"); ["nr", "nn", "ne", "nd", "nf"].forEach(i => $("#" + i).value = ""); load(); } catch (er) { toast(er.message); }
    };
    load();
  }],
  attendance: ["Attendance", async v => {
    const stu = await api("/api/students");
    const opts = stu.filter(s => s.active).map(s => `<option value="${s.id}">${esc(s.roll_no)} - ${esc(s.name)}</option>`).join("");
    v.innerHTML = `<h1>Attendance</h1>
      <div class="panel"><b>Fingerprint attendance</b>
        <p class="muted">A fingerprint scanner sends its stored ID to the server. Type or scan the ID below to test the flow.</p>
        <div class="row"><label>Fingerprint ID<input id="fp" placeholder="e.g. FP001"></label><button id="scan" class="primary" style="margin:0">Verify and mark present</button></div>
        <p id="fpMsg" class="muted"></p></div>
      <div class="panel"><b>Manual attendance</b>
        <div class="row"><label>Student<select id="ms">${opts}</select></label>
        <label>Date<input id="md" type="date" value="${new Date().toISOString().slice(0, 10)}"></label>
        <label>Status<select id="mt"><option>Present</option><option>Absent</option><option>Leave</option></select></label>
        <button id="save" class="primary" style="margin:0">Save</button></div></div>`;
    $("#scan").onclick = async () => {
      try { const r = await api("/api/biometric", "POST", { fingerprint_id: $("#fp").value }); $("#fpMsg").textContent = r.message; toast(r.message); $("#fp").value = ""; }
      catch (e) { $("#fpMsg").textContent = e.message; }
    };
    $("#save").onclick = async () => {
      try { await api("/api/attendance", "POST", { student_id: $("#ms").value, date: $("#md").value, status: $("#mt").value }); toast("Attendance saved"); } catch (e) { toast(e.message); }
    };
  }],
  low: ["Low attendance", async v => {
    const d = await api("/api/low-attendance");
    v.innerHTML = `<h1>Low attendance alerts</h1><p class="muted">Students below ${d.threshold}% attendance.</p>${lowTable(d.students)}`;
  }],
  mine: ["My attendance", async v => { v.innerHTML = '<div id="detail"></div>'; showDetail(me.student_id); }]
};

const lowTable = rows => rows.length ? `<div class="panel"><table><tr><th>Roll no</th><th>Name</th><th>Present</th><th>Working days</th><th>Attendance</th></tr>` +
  rows.map(s => `<tr><td>${esc(s.roll_no)}</td><td>${esc(s.name)}</td><td>${s.present}</td><td>${s.total_days}</td><td>${pill(s)}</td></tr>`).join("") + "</table></div>"
  : `<div class="panel muted">Everyone is at or above the minimum.</div>`;

async function showDetail(id) {
  try {
    const { student: s, records } = await api(`/api/students/${id}/attendance`);
    $("#detail").innerHTML = `<h3>${esc(s.name)} (${esc(s.roll_no)})</h3>
      ${s.low ? `<p class="err">Low attendance: ${s.percentage}% is below the minimum. Attend regularly to recover.</p>` : ""}
      <div class="stats"><div class="stat"><b>${s.percentage}%</b><span>Attendance</span>${bar(s)}</div>
      <div class="stat"><b>${s.present}</b><span>Present</span></div><div class="stat"><b>${s.absent}</b><span>Absent</span></div>
      <div class="stat"><b>${s.on_leave}</b><span>Leave</span></div><div class="stat"><b>${s.total_days}</b><span>Working days</span></div></div>
      <div class="panel"><table><tr><th>Date</th><th>Status</th><th>Method</th></tr>${records.map(r => `<tr><td>${r.date}</td><td><span class="pill ${r.status}">${r.status}</span></td><td>${r.method}</td></tr>`).join("") || '<tr><td colspan="3" class="muted">No records yet.</td></tr>'}</table></div>`;
  } catch (e) { toast(e.message); }
}

function enter(user) {
  me = user; $("#login").hidden = true; $("#app").hidden = false;
  const tabs = me.role === "student" ? ["mine"] : ["dashboard", "students", "attendance", "low"];
  $("#nav").innerHTML = tabs.map(t => `<button data-t="${t}">${PAGES[t][0]}</button>`).join("");
  $("#nav").onclick = e => e.target.dataset.t && go(e.target.dataset.t);
  go(tabs[0]);
}
async function go(t) {
  tab = t; document.querySelectorAll("#nav button").forEach(b => b.classList.toggle("on", b.dataset.t === t));
  try { await PAGES[t][1]($("#view")); } catch (e) { $("#view").innerHTML = `<p class="err">${esc(e.message)}</p>`; }
}
$("#loginForm").onsubmit = async e => {
  e.preventDefault(); $("#loginErr").textContent = "";
  try { enter(await api("/api/login", "POST", { username: $("#u").value, password: $("#p").value, role: $("#r").value })); }
  catch (er) { $("#loginErr").textContent = er.message; }
};
$("#logout").onclick = async () => { await api("/api/logout", "POST"); location.reload(); };
api("/api/me").then(enter).catch(() => {});
