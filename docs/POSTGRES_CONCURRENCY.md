# PostgreSQL row-lock verification

`blog/tests/test_postgres_concurrency.py` uses TransactionTestCase and two real threaded API clients with separate connections. Requests synchronize before SELECT FOR UPDATE. Two PUTs with the same ETag must produce 200 + 412 and retain the winning revision. PUT versus DELETE must either keep the updated record and reject stale deletion (200 + 412), or delete it and reject the later update (204 + 404).

Configure POSTGRES_DB/USER/PASSWORD/HOST/PORT for an isolated PostgreSQL fixture and run `python manage.py test --noinput`. Django creates/drops `test_<POSTGRES_DB>`; the fixture role needs CREATEDB. Never point these variables at a production database. CI runs the whole Django suite against PostgreSQL 16 in a separate service job, alongside the existing SQLite checks. On SQLite, the two row-lock tests explicitly skip.

If-Match is optional for backward compatibility. The conflict guarantee applies when clients supply the ETag they read; clients omitting it explicitly accept last-writer behaviour. The test fixtures no longer supply hardcoded auto-increment IDs: PostgreSQL sequences do not advance after manually inserted IDs, unlike SQLite's usual allocation behaviour. This removes a fixture-only duplicate-key failure exposed by running the full suite on PostgreSQL.
