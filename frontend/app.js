// 학사 일정 AI 비서 프론트엔드 (바닐라 JS)
"use strict";

const API_BASE_URL = ((window.APP_CONFIG && window.APP_CONFIG.API_BASE_URL) || "http://localhost:8000").replace(/\/+$/, "");

const DEFAULT_VALUE = { 시험: 5, 과제: 4, 퀴즈: 3, 강의시청: 2, 법정교육: 1, 신청: 1, 개인: 1 };
const COLD_START_HINT_MS = 3000;

const $ = (sel) => document.querySelector(sel);

const state = {
  conversationId: null,
  sending: false,
  data: [],
  editingId: null,
  lastSavedId: null,
  keep2400: false,
  serverReady: false,
};

// ---------- 공통 유틸 ----------
async function api(path, options = {}) {
  const res = await fetch(API_BASE_URL + path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  let body = null;
  try { body = await res.json(); } catch (_) { /* 본문 없음 */ }
  if (!res.ok) throw new Error(errorMessage(res.status, body));
  markServerReady();
  return body;
}

function errorMessage(status, body) {
  const detail = body && body.detail;
  if (Array.isArray(detail)) {
    // Pydantic 422 검증 오류
    return detail.map((d) => `${d.loc[d.loc.length - 1]}: ${d.msg}`).join("\n");
  }
  if (typeof detail === "string") return detail;
  return `요청 실패 (HTTP ${status})`;
}

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else if (k === "text") node.textContent = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v);
  }
  for (const c of children) if (c != null) node.append(c);
  return node;
}

let toastTimer;
function toast(message) {
  const t = $("#toast");
  t.textContent = message;
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.hidden = true; }, 2500);
}

const WEEKDAYS = ["일", "월", "화", "수", "목", "금", "토"];
function formatDate(iso, withWeekday = true) {
  const [y, m, d] = iso.split("-").map(Number);
  const wd = WEEKDAYS[new Date(y, m - 1, d).getDay()];
  return withWeekday ? `${m}/${d}(${wd})` : `${m}/${d}`;
}

function todayKST() {
  // 서버와 같은 기준(Asia/Seoul)으로 오늘 날짜
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Seoul" }).format(new Date());
}

// ---------- 콜드스타트 안내 ----------
function showBanner(text, kind = "") {
  const b = $("#server-banner");
  b.className = "banner" + (kind ? " " + kind : "");
  $("#server-banner-text").textContent = text;
  b.hidden = false;
}

function markServerReady() {
  if (state.serverReady) return;
  state.serverReady = true;
  const b = $("#server-banner");
  if (!b.hidden) {
    showBanner("서버에 연결되었습니다.", "ok");
    setTimeout(() => { b.hidden = true; }, 1500);
  }
}

async function wakeServer() {
  // Render 무료 티어는 요청이 없으면 잠들기 때문에 첫 요청이 30초~1분 걸릴 수 있다.
  const hint = setTimeout(() => {
    if (!state.serverReady) {
      showBanner("서버를 깨우는 중입니다. 무료 서버라 첫 접속은 최대 1분 정도 걸릴 수 있어요.");
    }
  }, COLD_START_HINT_MS);
  for (let attempt = 0; attempt < 6; attempt++) {
    try {
      const res = await fetch(API_BASE_URL + "/health");
      if (res.ok) { clearTimeout(hint); markServerReady(); return true; }
    } catch (_) { /* 아직 깨어나는 중 */ }
    await new Promise((r) => setTimeout(r, 5000));
  }
  clearTimeout(hint);
  showBanner(`서버(${API_BASE_URL})에 연결할 수 없습니다. 잠시 후 새로고침해 주세요.`, "error");
  return false;
}

// ---------- 탭 ----------
function setupTabs() {
  document.querySelectorAll(".tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((b) => {
        const active = b === btn;
        b.classList.toggle("active", active);
        b.setAttribute("aria-selected", String(active));
        $("#tab-" + b.dataset.tab).hidden = !active;
      });
    });
  });
}

// ---------- 요약 ----------
async function loadSummary() {
  const box = $("#summary");
  try {
    renderSummary(await api("/api/data/summary"));
  } catch (e) {
    box.replaceChildren(el("p", { class: "muted small", text: "요약을 불러오지 못했습니다: " + e.message }));
  }
}

function renderSummary(s) {
  const box = $("#summary");
  if (!s.count) {
    box.replaceChildren(el("p", { class: "muted small", text: "아직 데이터가 없습니다. 데이터 관리 탭에서 일정을 추가하세요." }));
    return;
  }
  const t = s.trend;
  const rate = t.change_rate == null ? "" : ` (${t.change_rate > 0 ? "+" : ""}${Math.round(t.change_rate * 100)}%)`;
  const arrow = { 증가: "↑", 감소: "↓", 유지: "→" }[t.direction] || "";

  const stats = el("div", { class: "stat-grid" },
    stat("기간", `${formatDate(s.period.start, false)} ~ ${formatDate(s.period.end, false)}`, s.period.start.slice(0, 4)),
    stat("전체 일정", `${s.count}건`, `중요도 평균 ${s.value_stats.mean}`),
    stat("최근 2주 추세", `${arrow} ${t.direction}`, `주 ${t.recent_weekly_avg}건 vs ${t.previous_weekly_avg}건${rate}`, "trend-" + t.direction),
    stat("중요도", `${s.value_stats.min} ~ ${s.value_stats.max}`, "1(낮음) ~ 5(높음)"),
  );

  const cats = el("ul", { class: "cat-list" });
  for (const [k, v] of Object.entries(s.category_counts)) {
    if (v > 0) cats.append(el("li", { text: `${k} ${v}` }));
  }

  const maxWeek = Math.max(1, ...s.weekly_counts.map((w) => w.count));
  const weekly = el("div", { class: "weekly", title: "주별 일정 수" });
  for (const w of s.weekly_counts) {
    const recent = w.week_start >= t.recent_range.start.slice(0, 10) && w.week_start <= t.recent_range.end;
    weekly.append(el("div", {
      class: "bar" + (recent ? " recent" : ""),
      style: `height:${Math.round((w.count / maxWeek) * 100)}%`,
      title: `${w.week_start} 주: ${w.count}건`,
    }));
  }

  const up = el("ul", { class: "upcoming" });
  for (const u of s.upcoming) {
    up.append(el("li", {},
      el("span", { class: "d" + (u.date === s.today ? " today" : ""), text: u.date === s.today ? "오늘" : formatDate(u.date) }),
      el("span", { text: u.memo }),
    ));
  }
  if (!s.upcoming.length) up.append(el("li", { class: "muted", text: "다가오는 마감이 없습니다." }));

  box.replaceChildren(
    stats,
    section("분류별", cats),
    section("주별 일정 수", weekly),
    section(`다가오는 마감 (기준일 ${formatDate(s.today)})`, up),
  );
}

function stat(label, value, sub, cls = "") {
  return el("div", { class: "stat" },
    el("div", { class: "stat-label", text: label }),
    el("div", { class: "stat-value " + cls, text: value }),
    el("div", { class: "stat-sub", text: sub }),
  );
}

function section(title, content) {
  return el("div", { class: "summary-section" }, el("h3", { text: title }), content);
}

// ---------- 채팅 ----------
function clearWelcome() {
  const w = $("#welcome");
  if (w) w.remove();
}

function addMessage(role, content) {
  clearWelcome();
  const node = el("div", { class: "msg " + role, text: content });
  $("#messages").append(node);
  node.scrollIntoView({ block: "end" });
  return node;
}

function addTyping() {
  clearWelcome();
  const node = el("div", { class: "msg assistant", "aria-label": "답변 생성 중" },
    el("span", { class: "typing" }, el("span"), el("span"), el("span")),
    el("span", { class: "typing-label", text: "일정 데이터를 확인하는 중…" }),
  );
  $("#messages").append(node);
  node.scrollIntoView({ block: "end" });
  return node;
}

function setSending(sending) {
  state.sending = sending;
  $("#chat-send").disabled = sending;
  $("#chat-input").disabled = sending;
}

async function sendMessage(text) {
  text = text.trim();
  if (!text || state.sending) return;
  addMessage("user", text);
  $("#chat-input").value = "";
  autoGrow();
  setSending(true);
  const typing = addTyping();
  const slowHint = setTimeout(() => {
    typing.querySelector(".typing-label").textContent = "서버가 깨어나는 중이면 조금 더 걸릴 수 있어요…";
  }, 10000);
  try {
    const res = await api("/api/chat", {
      method: "POST",
      body: JSON.stringify({ message: text, conversation_id: state.conversationId }),
    });
    typing.remove();
    addMessage("assistant", res.reply);
    const isNew = state.conversationId !== res.conversation_id;
    state.conversationId = res.conversation_id;
    if (isNew) $("#chat-title").textContent = text.length > 30 ? text.slice(0, 29) + "…" : text;
    loadConversations();
  } catch (e) {
    typing.remove();
    addMessage("error", "오류: " + e.message);
  } finally {
    clearTimeout(slowHint);
    setSending(false);
    $("#chat-input").focus();
  }
}

function newChat() {
  state.conversationId = null;
  $("#chat-title").textContent = "새 대화";
  const msgs = $("#messages");
  msgs.replaceChildren();
  const welcome = el("div", { class: "welcome", id: "welcome" },
    el("p", { text: "새 대화를 시작하세요. 저장된 일정 데이터를 바탕으로 답합니다." }));
  msgs.append(welcome);
  highlightConversation();
  $("#chat-input").focus();
}

function autoGrow() {
  const ta = $("#chat-input");
  ta.style.height = "auto";
  ta.style.height = Math.min(ta.scrollHeight, 160) + "px";
}

function setupChat() {
  $("#chat-form").addEventListener("submit", (e) => {
    e.preventDefault();
    sendMessage($("#chat-input").value);
  });
  $("#chat-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
      e.preventDefault();
      sendMessage($("#chat-input").value);
    }
  });
  $("#chat-input").addEventListener("input", autoGrow);
  document.querySelectorAll(".chip").forEach((c) =>
    c.addEventListener("click", () => sendMessage(c.textContent)));
  $("#new-chat").addEventListener("click", newChat);
  $("#summary-refresh").addEventListener("click", loadSummary);
}

// ---------- 대화 기록 ----------
async function loadConversations() {
  const list = $("#conv-list");
  try {
    const items = await api("/api/conversations");
    list.replaceChildren(...items.map(convItem));
    $("#conv-empty").hidden = items.length > 0;
    highlightConversation();
  } catch (e) {
    list.replaceChildren(el("li", { class: "muted small", text: "불러오기 실패: " + e.message }));
  }
}

function convItem(c) {
  const when = new Date(c.created_at).toLocaleString("ko-KR", {
    month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit", timeZone: "Asia/Seoul",
  });
  return el("li", { class: "conv-item", "data-id": c.id },
    el("button", { type: "button", class: "conv-open", onclick: () => openConversation(c.id) },
      el("span", { class: "conv-title", text: c.title }),
      el("span", { class: "conv-meta", text: `${when} · 메시지 ${c.message_count}개` }),
    ),
    el("button", {
      type: "button", class: "conv-delete", title: "대화 삭제", "aria-label": "대화 삭제", text: "×",
      onclick: () => deleteConversation(c.id, c.title),
    }),
  );
}

function highlightConversation() {
  document.querySelectorAll(".conv-item").forEach((li) =>
    li.classList.toggle("active", li.dataset.id === state.conversationId));
}

async function openConversation(id) {
  if (state.sending) return;
  try {
    const conv = await api("/api/conversations/" + encodeURIComponent(id));
    state.conversationId = conv.id;
    $("#chat-title").textContent = conv.title;
    $("#messages").replaceChildren();
    conv.messages.forEach((m) => addMessage(m.role, m.content));
    highlightConversation();
    // 좁은 화면에서는 채팅 영역으로 이동
    $("#chat-form").scrollIntoView({ block: "nearest" });
  } catch (e) {
    toast("대화를 불러오지 못했습니다: " + e.message);
  }
}

async function deleteConversation(id, title) {
  if (!confirm(`"${title}" 대화를 삭제할까요?`)) return;
  try {
    await api("/api/conversations/" + encodeURIComponent(id), { method: "DELETE" });
    if (state.conversationId === id) newChat();
    toast("대화를 삭제했습니다.");
    loadConversations();
  } catch (e) {
    toast("삭제 실패: " + e.message);
  }
}

// ---------- 데이터 관리 ----------
const MEMO_RE = /^\s*\[([^\]]+)\]\s*(.*?)\s*(?:\(마감\s*(\d{1,2}):(\d{2})\))?\s*$/;

function buildMemo() {
  const cat = $("#f-category").value;
  const text = $("#f-text").value.trim();
  let time = $("#f-time").value; // "HH:MM" 또는 ""
  // 원래 '마감 24:00'인 일정을 수정할 때 시각을 건드리지 않았으면 24:00을 유지한다.
  if (state.keep2400 && time === "23:59") time = "24:00";
  return `[${cat}] ${text}` + (time ? ` (마감 ${time})` : "");
}

function updatePreview() {
  $("#f-preview").textContent = buildMemo();
}

function fillForm(item) {
  $("#f-date").value = item.date;
  $("#f-value").value = String(item.value);
  const m = item.memo.match(MEMO_RE);
  const categories = [...$("#f-category").options].map((o) => o.value);
  if (m && categories.includes(m[1])) {
    $("#f-category").value = m[1];
    $("#f-text").value = m[2];
    // 24:00 마감은 time 입력이 표현할 수 없어서 23:59로 바꿔 보여준다.
    const h = m[3] ? m[3].padStart(2, "0") : "";
    $("#f-time").value = h ? (h === "24" ? "23:59" : `${h}:${m[4]}`) : "";
    state.keep2400 = h === "24";
  } else {
    $("#f-category").value = "개인";
    $("#f-text").value = item.memo;
    $("#f-time").value = "";
  }
  updatePreview();
}

function resetForm() {
  state.editingId = null;
  state.keep2400 = false;
  $("#data-form").reset();
  $("#f-date").value = todayKST();
  $("#f-category").value = "개인";
  $("#f-value").value = String(DEFAULT_VALUE["개인"]);
  $("#data-form-title").textContent = "새 일정 추가";
  $("#data-submit").textContent = "추가";
  $("#data-cancel").hidden = true;
  updatePreview();
  renderDataTable();
}

function startEdit(item) {
  state.editingId = item.id;
  fillForm(item);
  $("#data-form-title").textContent = "일정 수정";
  $("#data-submit").textContent = "수정 저장";
  $("#data-cancel").hidden = false;
  setFormMsg("");
  renderDataTable();
  $("#data-form").scrollIntoView({ block: "nearest", behavior: "smooth" });
}

function setFormMsg(text, ok = false) {
  const p = $("#data-form-msg");
  p.textContent = text;
  p.classList.toggle("ok", ok);
}

function validateForm() {
  // 서버(Pydantic)에서도 검증하지만, 사용자가 바로 알 수 있게 화면에서도 확인한다.
  const date = $("#f-date").value;
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) return "날짜를 선택하세요.";
  if (!$("#f-text").value.trim()) return "내용을 입력하세요.";
  if (buildMemo().length > 200) return "memo는 200자 이하여야 합니다.";
  return "";
}

async function submitData(e) {
  e.preventDefault();
  const err = validateForm();
  if (err) { setFormMsg(err); return; }
  const body = JSON.stringify({
    date: $("#f-date").value,
    value: Number($("#f-value").value),
    memo: buildMemo(),
  });
  const editing = state.editingId;
  $("#data-submit").disabled = true;
  try {
    const saved = editing
      ? await api("/api/data/" + encodeURIComponent(editing), { method: "PUT", body })
      : await api("/api/data", { method: "POST", body });
    state.lastSavedId = saved.id;
    toast(editing ? "수정했습니다." : "추가했습니다.");
    resetForm();
    setFormMsg(editing ? "저장 완료: 일정을 수정했습니다." : "저장 완료: 새 일정을 추가했습니다.", true);
    await loadData();
    const row = document.querySelector(`#data-tbody tr[data-id="${CSS.escape(saved.id)}"]`);
    if (row) row.scrollIntoView({ block: "center", behavior: "smooth" });
    loadSummary();
  } catch (e2) {
    setFormMsg(e2.message);
  } finally {
    $("#data-submit").disabled = false;
  }
}

async function deleteData(item) {
  if (!confirm(`삭제할까요?\n${item.date} ${item.memo}`)) return;
  try {
    await api("/api/data/" + encodeURIComponent(item.id), { method: "DELETE" });
    if (state.editingId === item.id) resetForm();
    toast("삭제했습니다.");
    await loadData();
    loadSummary();
  } catch (e) {
    toast("삭제 실패: " + e.message);
  }
}

async function loadData() {
  try {
    state.data = await api("/api/data");
    refreshCategoryFilter();
    renderDataTable();
  } catch (e) {
    $("#data-tbody").replaceChildren(el("tr", {}, el("td", { colspan: "4", class: "muted", text: "불러오기 실패: " + e.message })));
  }
}

function refreshCategoryFilter() {
  const sel = $("#filter-category");
  const current = sel.value;
  const cats = [...new Set(state.data.map((d) => (d.memo.match(/^\s*\[([^\]]+)\]/) || [, "기타"])[1]))];
  sel.replaceChildren(el("option", { value: "", text: "전체 분류" }),
    ...cats.map((c) => el("option", { value: c, text: c })));
  sel.value = cats.includes(current) ? current : "";
}

function renderDataTable() {
  const cat = $("#filter-category").value;
  const q = $("#filter-text").value.trim().toLowerCase();
  const today = todayKST();
  const rows = state.data.filter((d) =>
    (!cat || d.memo.startsWith(`[${cat}]`) || (cat === "기타" && !d.memo.trim().startsWith("["))) &&
    (!q || d.memo.toLowerCase().includes(q) || d.date.includes(q)));

  $("#data-count").textContent = rows.length === state.data.length
    ? `(${state.data.length}건)` : `(${rows.length} / ${state.data.length}건)`;

  const tbody = $("#data-tbody");
  if (!rows.length) {
    tbody.replaceChildren(el("tr", {}, el("td", { colspan: "4", class: "muted", text: "표시할 데이터가 없습니다." })));
    return;
  }
  tbody.replaceChildren(...rows.map((d) => {
    const cls = [
      d.date < today ? "past" : "",
      d.id === state.editingId ? "editing" : "",
      d.id === state.lastSavedId ? "saved" : "",
    ].join(" ").trim();
    return el("tr", { class: cls, "data-id": d.id },
      el("td", { text: `${d.date} ${formatDate(d.date).slice(-3)}` }),
      el("td", {}, el("span", { class: `imp imp-${d.value}`, text: String(d.value) })),
      el("td", { text: d.memo }),
      el("td", { class: "actions" },
        el("button", { type: "button", class: "btn btn-small btn-ghost", text: "수정", onclick: () => startEdit(d) }),
        " ",
        el("button", { type: "button", class: "btn btn-small btn-danger", text: "삭제", onclick: () => deleteData(d) }),
      ),
    );
  }));
}

function setupDataForm() {
  $("#data-form").addEventListener("submit", submitData);
  $("#data-cancel").addEventListener("click", () => { resetForm(); setFormMsg(""); });
  $("#f-category").addEventListener("change", () => {
    // 분류를 바꾸면 기본 중요도 규칙을 적용 (사용자가 다시 바꿀 수 있음)
    $("#f-value").value = String(DEFAULT_VALUE[$("#f-category").value] || 1);
    updatePreview();
  });
  $("#f-text").addEventListener("input", updatePreview);
  $("#f-time").addEventListener("input", () => { state.keep2400 = false; updatePreview(); });
  $("#filter-category").addEventListener("change", renderDataTable);
  $("#filter-text").addEventListener("input", renderDataTable);
  resetForm();
}

// ---------- 시작 ----------
async function init() {
  setupTabs();
  setupChat();
  setupDataForm();
  $("#server-banner-close").addEventListener("click", () => { $("#server-banner").hidden = true; });

  const ok = await wakeServer();
  if (!ok) return;
  loadSummary();
  loadConversations();
  loadData();
}

document.addEventListener("DOMContentLoaded", init);
