# Blog API — backend блога на Django

Тестовый backend блога на Django и Django Ninja. При `DJANGO_API_DOCS=1` API-документация доступна по адресу `http://localhost:8000/api/docs`; в production её следует отключить.

## Быстрый запуск в Windows

Дважды щёлкните `START.bat` в корне проекта. Скрипт автоматически:

- при доступном Docker создаст `.env`, поднимет Django и PostgreSQL через Docker Compose и откроет API-документацию;
- без Docker подготовит `.venv`, выполнит миграции, запустит локальный сервер с SQLite и также откроет API-документацию.

Для остановки дважды щёлкните `STOP.bat`. Локальный SQLite — только удобный режим разработки; штатный контейнерный запуск использует PostgreSQL.

## Запуск в Docker

```bash
cp .env.example .env
# Сгенерируйте значения DJANGO_SECRET_KEY и POSTGRES_PASSWORD:
python -c "import secrets; print(secrets.token_urlsafe(50))"
docker compose up --build
```

PostgreSQL поднимается вместе с приложением, миграции выполняются автоматически. Для входа в админ-панель создайте суперпользователя:

```bash
docker compose exec web python manage.py createsuperuser
```

Админ-панель: `http://localhost:8000/admin/`.

## Локальный запуск и тесты

```bash
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py test
python manage.py runserver
```

Без переменных PostgreSQL проект использует SQLite только для локальной разработки и тестов. Настройки окружения перечислены в `.env.example`.

## Аутентификация

Регистрация и вход возвращают случайный токен ровно из 256 символов. В базе хранится только SHA-256 digest токена; токен действует 30 дней и ротируется при каждом входе. Для защищённых ручек передавайте его в заголовке:

```text
X-API-Token: <token>
```

При каждом входе токен ротируется, при выходе удаляется.

Ответы создания, чтения и обновления статьи содержат `ETag`. Клиент может передать его в
`If-Match` при `PUT` или `DELETE`; устаревшая версия получает `412`. Удаление статьи с
комментариями других пользователей отклоняется с `409`, чтобы не удалять чужие данные.

## Ручки

| Метод | URL | Доступ |
|---|---|---|
| POST | `/api/auth/register` | публичный |
| POST | `/api/auth/login` | публичный |
| POST | `/api/auth/logout` | по токену |
| GET, POST | `/api/articles` | чтение публичное, создание по токену |
| GET, PUT, DELETE | `/api/articles/{id}` | чтение публичное, изменение владельцем |
| GET, POST | `/api/comments` | чтение публичное, создание по токену |
| GET, PUT, DELETE | `/api/comments/{id}` | чтение публичное, изменение владельцем |

Логи HTTP-запросов пишутся в stdout с уровнями `INFO`, `WARNING`, `ERROR`. Отдельный audit-лог фиксирует вход, выход и CRUD пользователей, статей и комментариев, включая действия из Django Admin. Login/register и вход в админку ограничены по частоте.

После перевода домена и всех его поддоменов на HTTPS установите `DJANGO_HTTPS=1`: это включает redirect, secure cookies и годовой HSTS с `includeSubDomains; preload`. За доверенным reverse proxy также установите `DJANGO_TRUST_HTTPS_PROXY=1`, задайте число доверенных proxy в `NINJA_NUM_PROXIES` и перечислите HTTPS origins в `DJANGO_CSRF_TRUSTED_ORIGINS`.

Опциональные бонусы `django-ninja-jwt`, CI/CD и VPS-деплой намеренно не добавлены: базовое требование использует собственный 256-символьный токен, а инфраструктура назначения не задана.

Результаты security review и CycloneDX SBOM находятся в каталоге [`security`](../security/REPORT.md).

## Текущий режим работы
API предоставляет собственные токены, права владельца, админ-панель и ETag. Отдельный клиент не входит в репозиторий. Лимиты запросов действуют в памяти процесса; для нескольких процессов нужен общий кеш. Локальные замеры не являются результатом работы под эксплуатационной нагрузкой.
