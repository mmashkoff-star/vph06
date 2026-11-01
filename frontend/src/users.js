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

function setStatus(id, text, kind) {
  const node = document.getElementById(id);
  if (!node) return;
  node.hidden = false;
  node.textContent = text;
  node.dataset.kind = kind || "";
}

async function readError(res) {
  const data = await res.json().catch(() => ({}));
  const detail = data.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((item) => item.msg || "ошибка").join("; ");
  return `сервер ответил ${res.status}`;
}

function renderUsers(list, users, meId) {
  list.innerHTML = users.map((user) => `
    <article class="admin-card user-card" data-id="${esc(user.id)}">
      <div class="admin-card-head">
        <strong>${esc(user.login)}${user.id === meId ? " · вы" : ""}</strong>
        <span>#${esc(user.id)}</span>
      </div>
      <div class="row row-3">
        <label>Логин
          <input data-field="login" value="${esc(user.login)}" required minlength="3" maxlength="64">
        </label>
        <label>E-mail
          <input data-field="email" type="email" value="${esc(user.email || "")}" required maxlength="254">
        </label>
        <label>Новый пароль, если меняете
          <input data-field="password" type="password" minlength="8" autocomplete="new-password" placeholder="оставить как есть">
        </label>
      </div>
      <div class="admin-card-actions">
        <button type="button" class="ghost" data-save>Сохранить</button>
        <button type="button" class="danger" data-remove ${users.length <= 1 ? "disabled" : ""}>Удалить</button>
      </div>
    </article>
  `).join("");
}

async function boot() {
  if (!getToken()) {
    location.replace("/login.html");
    return;
  }

  const who = document.getElementById("who");
  const list = document.getElementById("users-list");
  let me = null;

  document.getElementById("logout-btn").addEventListener("click", () => {
    clearToken();
    location.replace("/login.html");
  });

  if (new URLSearchParams(location.search).get("welcome") === "1") {
    setStatus("welcome", "Зарегистрировали первого админа. Смените пароль, если этот вход был временным.", "ok");
  }

  try {
    const meRes = await api("/api/auth/me");
    if (!meRes.ok) throw new Error(await readError(meRes));
    me = await meRes.json();
    if (who) who.textContent = me.login;
    document.getElementById("me-login").textContent = me.login;
  } catch {
    return;
  }

  const loadUsers = async () => {
    const res = await api("/api/admins");
    if (!res.ok) throw new Error(await readError(res));
    renderUsers(list, await res.json(), me.id);
  };

  document.getElementById("password-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const currentPassword = document.getElementById("current-password").value;
    const next = document.getElementById("new-password").value;
    const again = document.getElementById("new-password-2").value;
    if (next !== again) {
      setStatus("password-status", "Новый пароль и подтверждение не совпадают.", "err");
      return;
    }
    const btn = document.getElementById("password-btn");
    btn.disabled = true;
    setStatus("password-status", "Сохраняем пароль…", "");
    try {
      const res = await api("/api/auth/password", {
        method: "POST",
        body: JSON.stringify({ current_password: currentPassword, new_password: next }),
      });
      if (!res.ok) throw new Error(await readError(res));
      event.target.reset();
      setStatus("password-status", "Пароль изменён. Дальше входите с новым.", "ok");
    } catch (error) {
      setStatus("password-status", String(error.message || error), "err");
    } finally {
      btn.disabled = false;
    }
  });

  document.getElementById("add-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const btn = document.getElementById("add-user-btn");
    btn.disabled = true;
    setStatus("users-status", "Добавляем…", "");
    try {
      const res = await api("/api/admins", {
        method: "POST",
        body: JSON.stringify({
          login: document.getElementById("add-login").value.trim(),
          email: document.getElementById("add-email").value.trim(),
          password: document.getElementById("add-password").value,
        }),
      });
      if (!res.ok) throw new Error(await readError(res));
      event.target.reset();
      await loadUsers();
      setStatus("users-status", "Администратор добавлен.", "ok");
    } catch (error) {
      setStatus("users-status", String(error.message || error), "err");
    } finally {
      btn.disabled = false;
    }
  });

  list.addEventListener("click", async (event) => {
    const card = event.target.closest(".user-card");
    if (!card) return;
    const adminId = Number(card.dataset.id);
    const login = card.querySelector("[data-field=login]").value.trim();
    const email = card.querySelector("[data-field=email]").value.trim();
    const password = card.querySelector("[data-field=password]").value;
    if (event.target.closest("[data-save]")) {
      const body = { login, email };
      if (password) body.password = password;
      setStatus("users-status", "Сохраняем пользователя…", "");
      try {
        const res = await api(`/api/admins/${adminId}`, {
          method: "PATCH",
          body: JSON.stringify(body),
        });
        if (!res.ok) throw new Error(await readError(res));
        const saved = await res.json();
        if (saved.id === me.id && who) who.textContent = saved.login;
        if (saved.id === me.id) document.getElementById("me-login").textContent = saved.login;
        await loadUsers();
        setStatus("users-status", "Пользователь сохранён.", "ok");
      } catch (error) {
        setStatus("users-status", String(error.message || error), "err");
      }
      return;
    }
    if (event.target.closest("[data-remove]")) {
      if (!confirm(`Удалить администратора «${login}»?`)) return;
      setStatus("users-status", "Удаляем…", "");
      try {
        const res = await api(`/api/admins/${adminId}`, { method: "DELETE" });
        if (!res.ok) throw new Error(await readError(res));
        if (adminId === me.id) {
          clearToken();
          location.replace("/login.html");
          return;
        }
        await loadUsers();
        setStatus("users-status", "Администратор удалён.", "ok");
      } catch (error) {
        setStatus("users-status", String(error.message || error), "err");
      }
    }
  });

  try {
    await loadUsers();
  } catch (error) {
    setStatus("users-status", String(error.message || error), "err");
  }
}

boot();
