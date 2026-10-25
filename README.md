# Django Blog API

Provide users, articles and comments through an ownership-aware REST API.


## Implemented

- Registration, login/logout and CRUD for articles and comments.
- Hashed expiring API tokens, rotation, ownership checks and audit records.
- ETag/If-Match support, pagination and Django admin.

## Stack and architecture

Python, Django, Django Ninja and SQLite/PostgreSQL.

## Technical mechanisms and security

- `blog/api.py` validates input and checks ownership on mutations. Tokens are stored as hashes, not reusable plaintext credentials.
- Transactional writes use row locking where supported. PostgreSQL and local SQLite are configured separately.
- Existing migrations and an immutable previous-version upgrade fixture check persistence across upgrades.

## Local setup

Python 3.12.14 (see `.python-version`). Activate the virtual environment before the remaining commands.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
python -m pip install -c requirements-lock.txt -r requirements.txt
python manage.py migrate
python manage.py runserver 127.0.0.1:8000
```

## Configuration

Use [.env.example](.env.example) for supported configuration and keep secrets outside Git. See [configuration details](docs/TECHNICAL.md) for loading settings and optional services.

## Database and upgrades

Run the migration command above before serving requests. Existing records are retained; tests check upgrading an immutable earlier version.

## Verification

```bash
python manage.py test
python tests/check_contract.py
python tests/check_upgrade.py
python -m pip check
```

Existing Django tests exercise tokens, ownership, validation and conditional updates. OpenAPI and previous-version migration checks remain enabled.

CI installs locked dependencies and runs the configured checks; documentation checks also validate local links/images. Python dependency auditing uses `pip-audit --disable-pip --no-deps --strict -r requirements-lock.txt`. A passing scanner only reports known advisories at the time of the run.

## Limits and next steps

- If-Match is optional: clients that omit it do not obtain optimistic conflict detection. SQLite does not implement PostgreSQL row-level select_for_update semantics.
- Rate limits are per-process. A public deployment needs HTTPS, deployment-specific origins/hosts, secret configuration and shared limits where appropriate.

## Further documentation

[Audit findings and follow-up](docs/AUDIT_2026_10.md) · [Technical reference](docs/TECHNICAL.md) · [Change history](CHANGELOG.md)

[API request/response example](docs/API_EXAMPLE.md)

## PostgreSQL verification

See [PostgreSQL concurrency checks](docs/POSTGRES_CONCURRENCY.md) for isolated test setup, CI and the exact concurrency guarantees.
