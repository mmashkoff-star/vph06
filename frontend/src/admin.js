import { api, clearToken, getToken } from "./auth.js";

function esc(value) {
  return String(value).replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[ch]));
}

function money(value) {
  return new Intl.NumberFormat("ru-RU").format(Number(value) || 0) + " ₽";
}

function slug(title, index) {
  const raw = String(title || "").trim().toLowerCase();
  const key = raw.replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  return key || `svc-${index + 1}`;
}

function emptyService() {
  return {
    key: "",
    title: "",
    description: "",
    work_types: [],
    budget_min: "200000",
    budget_max: "6000000",
    budget_step: "50000",
  };
}

function readCard(card, index) {
  const title = card.querySelector("[data-field=title]").value.trim();
  return {
    key: card.querySelector("[data-field=key]").value.trim() || slug(title, index),
    title,
    description: card.querySelector("[data-field=description]").value.trim(),
    work_types: card.querySelector("[data-field=work_types]").value.split(",").map((item) => item.trim()).filter(Boolean),
    budget_min: card.querySelector("[data-field=budget_min]").value.trim(),
    budget_max: card.querySelector("[data-field=budget_max]").value.trim(),
    budget_step: card.querySelector("[data-field=budget_step]").value.trim(),
  };
}

function validate(services) {
  if (!services.length) return "Добавьте хотя бы одну услугу.";
  for (const item of services) {
    if (!item.title) return "У каждой услуги должно быть название.";
    const min = Number(item.budget_min);
    const max = Number(item.budget_max);
    const step = Number(item.budget_step);
    if (!(min > 0) || !(max > 0) || !(step > 0)) {
      return `У услуги «${item.title}» заполните диапазон и шаг числами больше нуля.`;
    }
    if (min >= max) return `У услуги «${item.title}» минимум должен быть меньше максимума.`;
    if (step > max - min) return `У услуги «${item.title}» шаг больше ширины диапазона.`;
  }
  return "";
}

function renderList(list, services) {
  list.innerHTML = services.map((item, index) => `
    <article class="admin-card" data-index="${index}">
      <div class="admin-card-head">
        <strong>${esc(item.title || "Новая услуга")}</strong>
        <span>${esc(money(item.budget_min))} — ${esc(money(item.budget_max))}</span>
      </div>
      <input type="hidden" data-field="key" value="${esc(item.key || "")}">
      <div class="row row-2">
        <label>Название
          <input data-field="title" value="${esc(item.title || "")}" required>
        </label>
        <label>Типы работ, через запятую
          <input data-field="work_types" value="${esc((item.work_types || []).join(", "))}" placeholder="Диагностика, Плановое ТО">
        </label>
      </div>
      <label>Описание
        <textarea data-field="description" placeholder="Коротко, как на карточке формы">${esc(item.description || "")}</textarea>
      </label>
      <div class="row row-3">
        <label>Минимум, ₽
          <input data-field="budget_min" inputmode="numeric" value="${esc(item.budget_min || "")}">
        </label>
        <label>Максимум, ₽
          <input data-field="budget_max" inputmode="numeric" value="${esc(item.budget_max || "")}">
        </label>
        <label>Шаг, ₽
          <input data-field="budget_step" inputmode="numeric" value="${esc(item.budget_step || "")}">
        </label>
      </div>
      <div class="admin-card-actions">
        <button type="button" class="ghost" data-up ${index === 0 ? "disabled" : ""}>Выше</button>
        <button type="button" class="ghost" data-down ${index === services.length - 1 ? "disabled" : ""}>Ниже</button>
        <button type="button" class="danger" data-remove>Удалить</button>
      </div>
    </article>
  `).join("");
}

function collect(list) {
  return [...list.querySelectorAll(".admin-card")].map((card, index) => readCard(card, index));
}

function setStatus(node, text, kind) {
  node.textContent = text;
  node.dataset.kind = kind || "";
}

function formatDuration(seconds) {
  const total = Math.max(0, Math.round(Number(seconds) || 0));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const rest = total % 60;
  if (hours) return `${hours} ч ${minutes} мин ${rest} сек`;
  if (minutes) return `${minutes} мин ${rest} сек`;
  return `${rest} сек`;
}

function parseCursorPoints(raw) {
  let data;
  try {
    data = JSON.parse(raw || "[]");
  } catch {
    return [];
  }
  if (!Array.isArray(data)) return [];
  const points = [];
  for (const item of data) {
    let x;
    let y;
    let width = 1;
    let height = 1;
    let scrollX = 0;
    let scrollY = 0;
    if (Array.isArray(item)) {
      [x, y, width, height, scrollX = 0, scrollY = 0] = item;
    } else if (item && typeof item === "object") {
      x = item.x;
      y = item.y;
      width = item.w;
      height = item.h;
      scrollX = item.sx || 0;
      scrollY = item.sy || 0;
    } else {
      continue;
    }
    x = Number(x);
    y = Number(y);
    width = Number(width) || 1;
    height = Number(height) || 1;
    scrollX = Number(scrollX) || 0;
    scrollY = Number(scrollY) || 0;
    if (!Number.isFinite(x) || !Number.isFinite(y)) continue;
    if (x === 0 && y === 0) continue;
    points.push({
      nx: (x + scrollX) / width,
      ny: (y + scrollY) / height,
    });
  }
  return points;
}

function parseClicks(raw) {
  try {
    const data = JSON.parse(raw || "{}");
    return data && typeof data === "object" && !Array.isArray(data) ? data : {};
  } catch {
    return {};
  }
}

function periodStats(rows, hours) {
  const since = Date.now() - hours * 3600 * 1000;
  const selected = rows.filter((row) => {
    const stamp = Date.parse(row.created_at || row.updated_at || "");
    return Number.isFinite(stamp) && stamp >= since;
  });
  const times = selected.map((row) => Number(row.time_on_page) || 0);
  const sum = times.reduce((acc, value) => acc + value, 0);
  return {
    count: selected.length,
    avg: selected.length ? sum / selected.length : 0,
    max: times.length ? Math.max(...times) : 0,
  };
}

function summarizeClicks(rows) {
  const totals = {};
  for (const row of rows) {
    const clicks = parseClicks(row.buttons_clicked);
    for (const [name, count] of Object.entries(clicks)) {
      totals[name] = (totals[name] || 0) + Number(count || 0);
    }
  }
  return Object.entries(totals)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6);
}

function renderTimes(node, rows) {
  const periods = [
    { key: "day", label: "За день", hours: 24 },
    { key: "week", label: "За неделю", hours: 24 * 7 },
    { key: "month", label: "За месяц", hours: 24 * 30 },
  ];
  node.innerHTML = periods.map((period) => {
    const stats = periodStats(rows, period.hours);
    return `<article class="stats-time">
      <span>${esc(period.label)}</span>
      <strong>${esc(formatDuration(stats.avg))}</strong>
      <em>среднее · макс. ${esc(formatDuration(stats.max))} · ${stats.count} сес.</em>
    </article>`;
  }).join("");
}

function drawHeatmap(canvas, points) {
  const wrap = canvas.parentElement;
  const cssW = Math.max(wrap.clientWidth - 8, 320);
  const maxNy = Math.max(1.15, ...points.map((point) => point.ny));
  const maxNx = Math.max(1, ...points.map((point) => point.nx));
  const cssH = Math.min(Math.max(380, Math.round(cssW * (maxNy / maxNx) * 0.62)), 680);
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  canvas.width = Math.floor(cssW * dpr);
  canvas.height = Math.floor(cssH * dpr);
  canvas.style.width = `${cssW}px`;
  canvas.style.height = `${cssH}px`;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.fillStyle = "#0b090c";
  ctx.fillRect(0, 0, cssW, cssH);
  ctx.strokeStyle = "rgba(196, 165, 116, .12)";
  for (let i = 1; i < 6; i += 1) {
    const x = (cssW / 6) * i;
    const y = (cssH / 6) * i;
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, cssH);
    ctx.moveTo(0, y);
    ctx.lineTo(cssW, y);
    ctx.stroke();
  }
  if (!points.length) {
    ctx.fillStyle = "rgba(179, 164, 143, .85)";
    ctx.font = "16px Manrope, sans-serif";
    ctx.fillText("Пока нет координат курсора", 24, 40);
    return;
  }
  const cols = 40;
  const rows = Math.max(22, Math.round(40 * (cssH / cssW)));
  const grid = Array.from({ length: rows }, () => Array(cols).fill(0));
  let peak = 1;
  for (const point of points) {
    const col = Math.min(cols - 1, Math.max(0, Math.floor((point.nx / maxNx) * cols)));
    const row = Math.min(rows - 1, Math.max(0, Math.floor((point.ny / maxNy) * rows)));
    grid[row][col] += 1;
    if (grid[row][col] > peak) peak = grid[row][col];
  }
  for (let row = 0; row < rows; row += 1) {
    for (let col = 0; col < cols; col += 1) {
      const count = grid[row][col];
      if (!count) continue;
      const heat = count / peak;
      const x = ((col + 0.5) / cols) * cssW;
      const y = ((row + 0.5) / rows) * cssH;
      const radius = 7 + heat * 26;
      const glow = ctx.createRadialGradient(x, y, 0, x, y, radius);
      glow.addColorStop(0, `rgba(255, 210, 140, ${0.22 + heat * 0.62})`);
      glow.addColorStop(0.4, `rgba(232, 150, 86, ${0.14 + heat * 0.34})`);
      glow.addColorStop(1, "rgba(196, 165, 116, 0)");
      ctx.fillStyle = glow;
      ctx.beginPath();
      ctx.arc(x, y, radius, 0, Math.PI * 2);
      ctx.fill();
    }
  }
}

function fio(lead) {
  return [lead.last_name, lead.first_name, lead.patronymic].filter(Boolean).join(" ") || "Без имени";
}

function phoneLink(phone) {
  return String(phone || "").replace(/[^\d+]/g, "");
}

function contactHref(lead) {
  const phone = phoneLink(lead.phone);
  const way = String(lead.preferred_contact || "").toLowerCase();
  if (way.includes("whatsapp") && phone) {
    return `https://wa.me/${phone.replace(/^\+/, "")}`;
  }
  if (way.includes("telegram") && phone) {
    return `https://t.me/${phone}`;
  }
  if (way.includes("email") && lead.email) {
    return `mailto:${lead.email}`;
  }
  return phone ? `tel:${phone}` : (lead.email ? `mailto:${lead.email}` : "");
}

function renderLeadOverview(node, summary) {
  const cards = [
    ["Всего заявок", summary.total || 0],
    ["Горячие", summary.hot || 0],
    ["Теплые / холодные", `${summary.warm || 0} / ${summary.cold || 0}`],
    ["Персональный менеджер", summary.personal_manager || 0],
  ];
  node.innerHTML = cards.map(([label, value]) => `
    <article class="lead-stat"><span>${esc(label)}</span><strong>${esc(value)}</strong></article>
  `).join("");
}

function renderLeads(body, leads) {
  body.innerHTML = leads.map((lead, index) => {
    const insight = lead.insight || {};
    const signals = (insight.signals || []).join(" · ");
    const href = contactHref(lead);
    const heat = insight.heat || "cold";
    const priority = { hot: "Высокий", warm: "Средний", cold: "Низкий" }[heat] || "Низкий";
    return `
      <tr data-lead-row="${lead.id}">
        <td>
          <span class="lead-name">${index + 1}</span>
          <span class="lead-meta">${esc(priority)}</span>
        </td>
        <td>
          <span class="lead-heat" data-heat="${esc(heat)}">${esc({ hot: "Горячий", warm: "Теплый", cold: "Холодный" }[heat] || "Холодный")} - ${esc(insight.score || 0)}</span>
          <span class="lead-meta">${esc(insight.department || "")}</span>
        </td>
        <td>
          <span class="lead-name">${esc(fio(lead))}</span>
          <span class="lead-meta">${esc(lead.phone || "нет телефона")} · ${esc(lead.preferred_contact || "контакт не выбран")}</span>
        </td>
        <td>
          ${esc([lead.make, lead.model, lead.year].filter(Boolean).join(" "))}
          <span class="lead-meta">${esc(lead.service || "услуга не указана")} · ${esc(lead.work_type || "тип работ не указан")}</span>
        </td>
        <td>
          ${esc(money(lead.budget))}
          <span class="lead-meta">${esc(lead.needed_by || "срок не указан")}</span>
        </td>
        <td>
          <p class="lead-decision">${esc(insight.worth_label || "")}</p>
          <span class="lead-meta">${esc(insight.personal_label || "")}</span>
        </td>
        <td><button type="button" class="ghost lead-open" data-open-lead="${lead.id}">Открыть</button></td>
      </tr>
      <tr class="lead-details" data-lead-details="${lead.id}" hidden>
        <td colspan="7">
          <div class="lead-grid">
            <p>Авто<br><strong>${esc([lead.make, lead.model, lead.year].filter(Boolean).join(" ") || "—")}</strong></p>
            <p>Комплектация<br><strong>${esc(lead.vehicle_details || "—")}</strong></p>
            <p>Услуга<br><strong>${esc(lead.service || "—")} / ${esc(lead.work_type || "—")}</strong></p>
            <p>Формат<br><strong>${esc(lead.visit_format || "—")} · ${esc(lead.booked_by || "роль не указана")}</strong></p>
            <p>Срок и время<br><strong>${esc(lead.needed_by || "—")} · ${esc(lead.convenient_time || "—")}</strong></p>
            <p>Комментарий<br><strong>${esc(lead.comments || "—")}</strong></p>
            <p>Сигналы<br><strong>${esc(signals || "мало данных")}</strong></p>
            <p>Почта<br><strong>${esc(lead.email || "—")}</strong></p>
          </div>
          <div class="lead-contacts">
            ${href ? `<a class="primary" href="${esc(href)}" target="_blank" rel="noreferrer">Связаться</a>` : ""}
            ${lead.phone ? `<a class="ghost" href="tel:${esc(phoneLink(lead.phone))}">Позвонить</a>` : ""}
            ${lead.email ? `<a class="ghost" href="mailto:${esc(lead.email)}">Написать на почту</a>` : ""}
          </div>
        </td>
      </tr>
    `;
  }).join("");
}

async function loadLeadQueue() {
  const overview = document.getElementById("leads-overview");
  const status = document.getElementById("leads-status");
  const body = document.getElementById("leads-body");
  if (!overview || !status || !body) return;
  try {
    const res = await api("/api/leads/queue?limit=100&offset=0");
    if (!res.ok) throw new Error(String(res.status));
    const data = await res.json();
    renderLeadOverview(overview, data.summary || {});
    renderLeads(body, data.leads || []);
    status.textContent = `В очереди ${data.summary?.total || 0} заявок. Сортировка по температуре льда.`;
  } catch {
    status.textContent = "Не удалось загрузить заявки.";
  }
}

function bindLeadQueue() {
  const body = document.getElementById("leads-body");
  if (!body) return;
  body.addEventListener("click", (event) => {
    const btn = event.target.closest("[data-open-lead]");
    if (!btn) return;
    const id = btn.getAttribute("data-open-lead");
    const row = body.querySelector(`[data-lead-details="${id}"]`);
    if (!row) return;
    const open = row.hidden;
    body.querySelectorAll("[data-lead-details]").forEach((node) => {
      node.hidden = true;
    });
    row.hidden = !open;
    btn.textContent = open ? "Скрыть" : "Открыть";
  });
}

function showView(name) {
  document.querySelectorAll("[data-panel]").forEach((panel) => {
    panel.hidden = panel.dataset.panel !== name;
  });
  document.querySelectorAll("[data-view]").forEach((btn) => {
    btn.classList.toggle("is-active", btn.dataset.view === name);
  });
}

async function loadFormStats() {
  const status = document.getElementById("stats-status");
  const times = document.getElementById("stats-times");
  const clicks = document.getElementById("stats-clicks");
  const canvas = document.getElementById("stats-heatmap");
  if (!status || !times || !clicks || !canvas) return;
  status.textContent = "Загружаем метрики…";
  times.innerHTML = "";
  clicks.textContent = "";
  drawHeatmap(canvas, []);
  try {
    const res = await api("/api/behavior-metrics/?limit=500&offset=0");
    if (!res.ok) throw new Error(String(res.status));
    const rows = await res.json();
    const list = Array.isArray(rows) ? rows : [];
    const points = list.flatMap((row) => parseCursorPoints(row.cursor_positions));
    renderTimes(times, list);
    const top = summarizeClicks(list);
    clicks.textContent = top.length
      ? `Чаще нажимали: ${top.map(([name, count]) => `${name} × ${count}`).join(" · ")}`
      : "Кликов по кнопкам пока нет.";
    status.textContent = list.length
      ? `Сессий на форме: ${list.length}. Точек курсора на карте: ${points.length}.`
      : "Записей статистики ещё нет.";
    requestAnimationFrame(() => drawHeatmap(canvas, points));
  } catch {
    status.textContent = "Не удалось загрузить статистику.";
  }
}

function bindAdminNav() {
  document.querySelectorAll("[data-view]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const view = btn.dataset.view;
      showView(view);
      if (view === "stats") loadFormStats();
      if (view === "leads") loadLeadQueue();
    });
  });
}

async function boot() {
  if (!getToken()) {
    location.replace("/login.html");
    return;
  }

  const list = document.getElementById("list");
  const status = document.getElementById("status");
  const saveBtn = document.getElementById("save-btn");
  const who = document.getElementById("who");
  let settingsId = 1;
  let defaults = { budget_min: "200000", budget_max: "6000000", budget_step: "50000" };

  document.getElementById("logout-btn").addEventListener("click", () => {
    clearToken();
    location.replace("/login.html");
  });
  bindAdminNav();
  bindLeadQueue();
  showView("leads");
  loadLeadQueue();

  try {
    const meRes = await api("/api/auth/me");
    if (!meRes.ok) throw new Error(String(meRes.status));
    const me = await meRes.json();
    if (who) who.textContent = me.login;
  } catch {
    return;
  }

  const refresh = (services) => renderList(list, services);

  list.addEventListener("click", (event) => {
    const card = event.target.closest(".admin-card");
    if (!card) return;
    const services = collect(list);
    const index = Number(card.dataset.index);
    if (event.target.closest("[data-remove]")) {
      services.splice(index, 1);
      refresh(services);
      return;
    }
    if (event.target.closest("[data-up]") && index > 0) {
      [services[index - 1], services[index]] = [services[index], services[index - 1]];
      refresh(services);
      return;
    }
    if (event.target.closest("[data-down]") && index < services.length - 1) {
      [services[index + 1], services[index]] = [services[index], services[index + 1]];
      refresh(services);
    }
  });

  document.getElementById("add-btn").addEventListener("click", () => {
    const services = collect(list);
    services.push({ ...emptyService(), ...defaults, key: `svc-${Date.now()}` });
    refresh(services);
    list.lastElementChild?.scrollIntoView({ behavior: "smooth", block: "center" });
  });

  saveBtn.addEventListener("click", async () => {
    const services = collect(list);
    const error = validate(services);
    if (error) {
      setStatus(status, error, "err");
      refresh(services);
      return;
    }
    saveBtn.disabled = true;
    setStatus(status, "Сохраняем…", "");
    try {
      const res = await api(`/api/admin/${settingsId}`, {
        method: "PATCH",
        body: JSON.stringify({ services }),
      });
      if (!res.ok) throw new Error(String(res.status));
      const saved = await res.json();
      settingsId = saved.id || settingsId;
      refresh(saved.services || services);
      setStatus(status, "Сохранено. Форма записи уже берёт этот список.", "ok");
    } catch {
      setStatus(status, "Не удалось сохранить. Проверьте API и попробуйте ещё раз.", "err");
      refresh(services);
    } finally {
      saveBtn.disabled = false;
    }
  });

  try {
    const res = await api("/api/admin");
    if (!res.ok) throw new Error(String(res.status));
    const data = await res.json();
    settingsId = data.id || 1;
    defaults = {
      budget_min: data.budget_min || defaults.budget_min,
      budget_max: data.budget_max || defaults.budget_max,
      budget_step: data.budget_step || defaults.budget_step,
    };
    refresh(data.services && data.services.length ? data.services : [emptyService()]);
    setStatus(status, "Загружены текущие услуги. Правки применятся после «Сохранить».", "");
  } catch {
    refresh([emptyService()]);
    setStatus(status, "Не удалось загрузить настройки. Можно заполнить список и сохранить.", "err");
  }
}

boot();
