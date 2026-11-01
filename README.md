# Deluxe Auto

Закрытый сайт записи в ателье для элитных авто. Тёплые клиенты оставляют заявку на визит; данные остаются на сервере.

Рабочий контур: **Nginx :80 → статика фронта и `/api`**, FastAPI, Postgres. Backend не публикует порты: с хоста и из интернета `:8000` недоступен, API живёт только через Nginx. Swagger, pgAdmin и Docker Registry в рабочий контур не входят.

## Адреса

Подставьте IP сервера вместо `SERVER_IP` (в `.env`).

| Что | URL |
|---|---|
| Форма записи | `http://SERVER_IP/` |
| Админ | `http://SERVER_IP/admin` → вход `/login` (JWT) |
| Пользователи / смена пароля | `http://SERVER_IP/users` |

По умолчанию в админке открывается **очередь заявок**. В шапке: «Статистика формы» и «Услуги и диапазон цен».

С хоста открыт только **порт 80**. `/docs`, `/redoc`, `/openapi.json`, `/pgadmin/` и порт **5000** закрыты (404 / connection refused).

## Состав

```
internet
  └─ Nginx :80
        ├─ frontend/dist     форма, /admin, /login, /users
        └─ /api/*            → backend :8000 (сеть app, без проброса на хост)
              └─ postgres :5432   только сеть data
```

Сети Compose: `edge` (выход в интернет у Nginx), `app` и `data` (внутренние).

Не поднимаются без явного профиля:

```bash
docker compose --profile tools up -d pgadmin      # /pgadmin в nginx сейчас выключен
docker compose --profile registry up -d registry  # порт 5000 в nginx снят
```

## Запуск

Нужны Docker Compose и файл `.env` (не в git).

```bash
cp .env.example .env
# Пароли с символом $ только в одинарных кавычках: POSTGRES_PASSWORD='YourPass$word'
chmod 600 .env
docker compose up -d postgres backend nginx
```

На VPS ~700 МБ RAM держите только эти три сервиса. После смены кода backend образ лучше не пересобирать на этой машине: скопируйте файлы в контейнер и `docker restart deluxe_backend`. Иначе контейнер может остаться на старой схеме колонок.

`ENABLE_DOCS=false` — документация API снаружи не отдаётся.

## Админка

Вход: логин и пароль, JWT в `sessionStorage`. Кнопка «Зарегистрироваться» есть, только пока таблица `admins` пуста. E-mail обязателен при регистрации и при добавлении пользователя, на экране входа его нет.

Очередь заявок (`GET /api/leads/queue`):

- сводка: всего, горячие, теплые / холодные, персональный менеджер;
- сортировка по температуре (срок, бюджет, объём, роль, марка);
- столбцы: приоритет (номер + Высокий / Средний / Низкий), температура (`Горячий - 85`), клиент, авто, бюджет, решение;
- «Открыть» — карточка и связь (звонок, почта, WhatsApp / Telegram).

«Статистика формы» — среднее и макс. время за день / неделю / месяц и хитмап курсора из `behavior_metrics`.

«Услуги и диапазон цен» — список услуг, типы работ и бюджет на публичной форме.

## Форма записи

Шлёт заявку в `POST /api/leads` (плюс снимок `behavior` в таблицу `behaviors`). Каждую секунду уходит `POST /api/behavior-metrics/`: секунды на странице, клики по кнопкам, точка курсора. Одна сессия браузера — одна строка, она обновляется.

Тип работ и ползунок бюджета зависят от выбранной услуги.

## API

Только через Nginx, префикс `/api`. Прямого порта backend нет.

- `GET /api/health`
- `GET /api/auth/status` — есть ли хотя бы один админ
- `POST /api/auth/register` — первый админ, пока `admins` пуста
- `POST /api/auth/login` — логин/пароль → JWT
- `POST /api/auth/password`, `GET /api/auth/me`, CRUD `/api/admins` — `Authorization: Bearer …`
- `GET /api/admin` — услуги и бюджет (публично, для формы)
- `PATCH /api/admin/{id}` — сохранить услуги (JWT)
- `POST /api/leads` — заявка
- `GET /api/leads/queue` — заявки с температурой, отсортированные для админки
- `POST /api/behavior-metrics/` — посекундные метрики формы

Таблицы создаются при старте backend из SQL в docstring моделей: `leads`, `behaviors`, `behavior_metrics`, `admin_settings`, `admins`.

## Фронтенд

Сборка **не на маленьком VPS**, а локально. Nginx отдаёт `frontend/dist`.

```bash
cd frontend
npm install
npm run build
```

На VPS достаточно скопировать `src` → `dist/assets` и обновить html. Источники: `frontend/src`, `frontend/*.html`.

## Диск и память

VPS ~7 ГБ диска и ~700 МБ RAM. Журналы Docker ограничены. Часовой `scripts/disk-guard.sh` чистит кэш и journal, **тома не трогает**. `docker system prune` только при занятости диска ≥ 90%.

Не ставьте Node и не собирайте Vite на этом VPS.

Пароли с `$` в `.env` — в одинарных кавычках.

## Структура

```
backend/          FastAPI, модели, CRUD, скоринг заявок
frontend/         Vite, сборка в dist/
nginx/conf.d/     reverse proxy, только :80
scripts/          init-secrets.sh, disk-guard.sh
docker-compose.yml
```
