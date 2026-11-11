"""Independent logical backups and verified restore into an empty Django database.

Connection URLs are read only from the environment; no rows or credentials are logged.
"""
import argparse
import gzip
import hashlib
import io
import json
import os
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit, urlunsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def verified_url(value):
    url = urlsplit(value)
    if url.scheme not in {"postgres", "postgresql"} or not url.hostname:
        raise ValueError("A PostgreSQL connection URL is required")
    query = dict(parse_qsl(url.query))
    query.update(sslmode="verify-full", sslrootcert="system")
    return urlunsplit(url._replace(query=urlencode(query)))


def configure(value):
    url = urlsplit(verified_url(value))
    os.environ.update(POSTGRES_DB=unquote(url.path[1:]), POSTGRES_USER=unquote(url.username or ""),
                      POSTGRES_PASSWORD=unquote(url.password or ""), POSTGRES_HOST=url.hostname,
                      POSTGRES_PORT=str(url.port or 5432), POSTGRES_SSLMODE="verify-full",
                      POSTGRES_SSLROOTCERT="system", DJANGO_DEBUG="1", DJANGO_HTTPS="0",
                      DJANGO_SETTINGS_MODULE="blog_project.settings")
    import django
    django.setup()


def canonical_dump():
    from django.core.management import call_command
    stream = io.StringIO()
    call_command("dumpdata", natural_foreign=True, natural_primary=True,
                 exclude=["contenttypes", "auth.permission"], stdout=stream, verbosity=0)
    rows = json.loads(stream.getvalue())
    # dumpdata orders models by natural-key dependencies; retain that order.
    model_order = {name: index for index, name in enumerate(dict.fromkeys(row["model"] for row in rows))}
    rows.sort(key=lambda row: (model_order[row["model"]], json.dumps(row, sort_keys=True)))
    return json.dumps(rows, sort_keys=True, separators=(",", ":")).encode(), dict(Counter(row["model"] for row in rows))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=["backup", "restore-check"])
    parser.add_argument("--snapshot", type=int)
    args = parser.parse_args()
    import psycopg
    from psycopg.types.json import Jsonb
    destination = verified_url(os.environ["BACKUP_DATABASE_URL"])
    if args.operation == "backup":
        source = os.environ["SOURCE_DATABASE_URL"]
        if urlsplit(source).hostname == urlsplit(destination).hostname:
            raise ValueError("Use an independent backup project")
        configure(source)
        from django.db import connection, transaction
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
                cursor.execute("SELECT app, name FROM django_migrations ORDER BY app,name")
                migrations = cursor.fetchall()
            payload, counts = canonical_dump()
        digest = hashlib.sha256(payload).hexdigest()
        with psycopg.connect(destination) as db:
            db.execute("CREATE TABLE IF NOT EXISTS django_backup_snapshots (id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, created_at timestamptz NOT NULL DEFAULT now(), revision text NOT NULL, sha256 text NOT NULL, model_counts jsonb NOT NULL, migrations jsonb NOT NULL, payload bytea NOT NULL)")
            row = db.execute("INSERT INTO django_backup_snapshots(revision,sha256,model_counts,migrations,payload) VALUES(%s,%s,%s,%s,%s) RETURNING id", (os.environ.get("SOURCE_REVISION", "unknown"), digest, Jsonb(counts), Jsonb(migrations), gzip.compress(payload, mtime=0))).fetchone()
        print(json.dumps({"snapshot": row[0], "sha256": digest, "model_counts": counts}))
    else:
        if not args.snapshot:
            raise ValueError("Choose the exact snapshot to restore")
        target = os.environ["RESTORE_DATABASE_URL"]
        if urlsplit(target).hostname == urlsplit(os.environ["SOURCE_DATABASE_URL"]).hostname:
            raise ValueError("Never restore onto the source project")
        with psycopg.connect(destination) as db:
            row = db.execute("SELECT sha256,migrations,payload FROM django_backup_snapshots WHERE id=%s", (args.snapshot,)).fetchone()
        if row is None:
            raise ValueError("Snapshot not found")
        payload = gzip.decompress(bytes(row[2]))
        if hashlib.sha256(payload).hexdigest() != row[0]:
            raise ValueError("Backup checksum mismatch")
        configure(target)
        from django.core.management import call_command
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")
            if cursor.fetchone()[0]:
                raise ValueError("Restore target must be a new empty database")
        call_command("migrate", interactive=False, verbosity=0)
        with connection.cursor() as cursor:
            cursor.execute("SELECT app,name FROM django_migrations ORDER BY app,name")
            if [list(item) for item in cursor.fetchall()] != row[1]:
                raise ValueError("Use the source revision: migration manifests differ")
        from unittest.mock import patch
        with patch("sys.stdin", io.StringIO(payload.decode())):
            call_command("loaddata", "-", format="json", verbosity=0)
        restored, counts = canonical_dump()
        if hashlib.sha256(restored).hexdigest() != row[0]:
            raise ValueError("Restored records differ from the backup")
        print(json.dumps({"snapshot": args.snapshot, "restored": True, "sha256": row[0], "model_counts": counts}))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # Connection errors may include credentials or private data; never print them.
        print(json.dumps({"status": "failed", "type": type(error).__name__}), file=sys.stderr)
        raise SystemExit(1)
