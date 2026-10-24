# Blog API — backend блога на Django

Предоставляет API пользователей, статей и комментариев.

**Проект:** Самостоятельная разработка.

![CI](https://github.com/memorim/django-blog-api/actions/workflows/ci.yml/badge.svg)

[Пример реального локального запроса и ответа](docs/API_EXAMPLE.md)

## Что работает
- Регистрация, вход и выход; статьи и комментарии с проверкой владельца.
- Хранение хеша API-токена, срок действия, ротация и аудит операций.
- ETag/If-Match для защиты от устаревшего изменения, админ-панель.

## Стек
Python, Django, Django Ninja, PostgreSQL/SQLite, Docker.

## Запуск и проверка
Python 3.12.14.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
python -m pip install -c requirements-lock.txt -r requirements.txt
python manage.py migrate
python manage.py test
python manage.py runserver
```

## Технические решения
- SQLite используется для локального запуска, PostgreSQL предусмотрен контейнерной конфигурацией.
- В development статика не требует production-манифеста; production использует WhiteNoise.

## Подробности
[API, конфигурация и исходные инструкции](docs/TECHNICAL.md).

[Результаты проверки этой версии](docs/VERIFICATION.md).

## Проверки и обновления
CI проверяет проект и ссылки на локальные материалы. Dependabot предлагает обновления зависимостей и Actions. [История изменений](CHANGELOG.md).

[Контракты API и обновление базы](docs/COMPATIBILITY.md): `python tests/check_contract.py && python tests/check_upgrade.py`.
