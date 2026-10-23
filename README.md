# Blog API — backend блога на Django

Предоставляет API пользователей, статей и комментариев.

**Тип:** Тестовое задание. Проект использовался реальными пользователями. В репозитории показана демонстрационная версия; масштаб и коммерческие показатели не заявляются.

![CI](https://github.com/memorim/django-blog-api/actions/workflows/ci.yml/badge.svg)

[Пример реального локального запроса и ответа](docs/API_EXAMPLE.md)

## Что работает
- Регистрация, вход и выход; статьи и комментарии с проверкой владельца.
- Хранение хеша API-токена, срок действия, ротация и аудит операций.
- ETag/If-Match для защиты от устаревшего изменения, админ-панель.

## Стек
Python, Django, Django Ninja, PostgreSQL/SQLite, Docker.

## Запуск и проверка
Python 3.12. Для PostgreSQL-варианта — Docker или доступная PostgreSQL.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py test
python manage.py runserver
```

## Технические решения
- SQLite используется для локального запуска, PostgreSQL предусмотрен контейнерной конфигурацией.
- В development статика не требует production-манифеста; production использует WhiteNoise.

## Границы готовности
- Проект изначально выполнен как тестовое задание. Отдельного клиентского приложения нет.
- Лимиты запросов используют память одного процесса; для нескольких процессов нужен общий кеш.
- Нагрузочные характеристики и работа под production-нагрузкой не измерялись.

## Подробности
[API, конфигурация и исходные инструкции](docs/TECHNICAL.md).

[Результаты проверки этой версии](docs/VERIFICATION.md).
