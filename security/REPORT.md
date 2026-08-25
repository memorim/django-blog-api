# Security review

Дата: 2026-08-24. Scope: Django/Django Ninja API, аутентификация и авторизация, admin, настройки deployment, Python dependency graph и OCI base images.

Использованные workflow: `conducting-api-security-testing` (OWASP API) и `analyzing-sbom-for-supply-chain-vulnerabilities`.

## Исправленные findings

| Severity | Finding | Исправление |
|---|---|---|
| High | Сырые бессрочные API-токены хранились в БД | В БД хранится SHA-256 digest; сырой 256-символьный токен выдаётся один раз, живёт 30 дней и ротируется при login |
| High | Official Python/PostgreSQL images содержали High/Critical CVE | Runtime переведён на проверенные Chainguard images с immutable digests; build stage отделён |
| Medium | Brute force login/register/admin | Native Django Ninja throttling и отдельный limiter admin login; proxy headers по умолчанию не доверяются |
| Medium | Mass assignment и неограниченный ввод | Pydantic `extra=forbid`, лимиты article/comment/request body |
| Medium | Неограниченный список комментариев и чрезмерный offset | Общая пагинация: limit 1..100, offset 0..10000 |
| Medium | Небезопасный production fallback secret и открытая schema | Production fail-closed для secret/hosts/PostgreSQL; OpenAPI выключен по умолчанию |
| Medium | Неполный HTTPS hardening | Secure cookies, redirect, HSTS, proxy/CSRF настройки при явном `DJANGO_HTTPS=1` |
| Medium | Плавающие зависимости и container tags | Все 15 Python-компонентов и OCI images закреплены версиями/digests; создан CycloneDX SBOM |
| Low | Login failures могли писать attacker-controlled username в лог | Username удалён из failure logs; токены и пароли не логируются |

## Проверки

- Django `check --deploy`: 0 issues.
- Bandit 1.9.4: 0 findings.
- `pip-audit` 2.10.1: 0 известных vulnerabilities в 15 runtime-компонентах.
- Grype 0.117.0, DB v6.1.9 от 2026-08-23: 0 vulnerabilities в Python SBOM; 0 vulnerabilities в PostgreSQL base image.
- Python runtime base: 0 High/Critical. Три Medium без доступных fix versions относятся к `stringprep`/IDNA2003, `urllib.request.HTTPPasswordMgr` и `poplib`; проект не использует эти модули или исходящие HTTP/POP3 credentials.
- 43 Django tests, включая BOLA, rotation/expiry, rate limiting, mass assignment, oversized input,
  SQL-injection payload и подтверждённые adversarial regression-сценарии.

CycloneDX v1.6 SBOM: [`sbom.cdx.json`](sbom.cdx.json).

Docker daemon в среде отсутствовал, поэтому собранный итоговый image не запускался. Оба закреплённых base image, Python SBOM и совместимость Linux CPython 3.14 wheels проверены независимо; после сборки в CI всё равно следует повторить `grype <final-image> --fail-on high`.
