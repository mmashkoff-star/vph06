import { setToken } from "./auth.js";

function setStatus(text, kind) {
  const node = document.getElementById("status");
  node.textContent = text;
  node.dataset.kind = kind || "";
}

function payload(includeEmail) {
  const body = {
    login: document.getElementById("login").value.trim(),
    password: document.getElementById("password").value,
  };
  if (includeEmail) body.email = document.getElementById("email").value.trim();
  return body;
}

async function send(path) {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload(path.endsWith("register"))),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = data.detail;
    if (typeof detail === "string") throw new Error(detail);
    if (Array.isArray(detail)) throw new Error(detail.map((item) => item.msg || item.detail || "ошибка").join("; "));
    throw new Error(`сервер ответил ${res.status}`);
  }
  return data;
}

function detailText(error) {
  if (Array.isArray(error.message)) return error.message.map((item) => item.msg || item).join("; ");
  return String(error.message || error);
}

async function boot() {
  const registerBtn = document.getElementById("register-btn");
  const loginBtn = document.getElementById("login-btn");
  const form = document.getElementById("auth-form");

  try {
    const res = await fetch("/api/auth/status");
    const data = await res.json();
    registerBtn.hidden = Boolean(data.has_admin);
    const emailWrap = document.getElementById("email-wrap");
    const emailInput = document.getElementById("email");
    emailWrap.hidden = Boolean(data.has_admin);
    emailInput.required = false;
    setStatus(
      data.has_admin
        ? "Введите логин и пароль администратора."
        : "Админов ещё нет. Зарегистрируйте первого — кнопка регистрации потом исчезнет.",
      "",
    );
  } catch {
    registerBtn.hidden = true;
    document.getElementById("email-wrap").hidden = true;
    setStatus("Не удалось проверить, есть ли админы. Можно попробовать войти.", "err");
  }

  const emailWrap = document.getElementById("email-wrap");
  const emailInput = document.getElementById("email");
  loginBtn.addEventListener("click", () => {
    emailInput.required = false;
  });
  registerBtn.addEventListener("click", () => {
    emailInput.required = !emailWrap.hidden;
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const submitter = event.submitter;
    const path = submitter === registerBtn ? "/api/auth/register" : "/api/auth/login";
    loginBtn.disabled = true;
    registerBtn.disabled = true;
    setStatus(path.endsWith("register") ? "Регистрируем…" : "Входим…", "");
    try {
      const data = await send(path);
      setToken(data.access_token);
      location.replace(path.endsWith("register") ? "/users.html?welcome=1" : "/admin.html");
    } catch (error) {
      setStatus(detailText(error), "err");
    } finally {
      loginBtn.disabled = false;
      registerBtn.disabled = false;
    }
  });
}

boot();
