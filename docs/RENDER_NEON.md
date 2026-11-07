# Render and Neon deployment

The backend supports Render's free Python web service with an independent Neon
PostgreSQL database. SQLite in the build filesystem is not used in production.
Both providers retain their own free-tier quotas; Render may sleep after idle
time and free compute hours are shared by the workspace.

Build with `pip install -c requirements-lock.txt -r requirements.txt` followed
by `python manage.py collectstatic --noinput`. Start with migrations and the
production check, then Gunicorn bound to `0.0.0.0:$PORT`. Keep database credentials
and DJANGO_SECRET_KEY in Render's environment, outside the repository.

Required runtime settings:

- DJANGO_DEBUG=0, DJANGO_HTTPS=1 and DJANGO_API_DOCS=0.
- DJANGO_ALLOWED_HOSTS is the actual assigned Render hostname, without wildcards.
- DJANGO_CSRF_TRUSTED_ORIGINS is its exact HTTPS origin.
- DJANGO_TRUST_HTTPS_PROXY=1 only behind Render's TLS edge; NINJA_NUM_PROXIES=1.
- POSTGRES_DB, USER, PASSWORD, HOST and PORT refer to the dedicated Neon database.
- POSTGRES_SSLMODE=verify-full and POSTGRES_SSLROOTCERT=/etc/ssl/certs/ca-certificates.crt
  verify the database server's identity with the Linux system certificate store.

After launch, check HTTPS, HSTS, private docs, token authentication, ownership,
ETag/If-Match conflicts and persistence after a restart. Source CI and local
production-setting tests do not substitute for those public deployment checks.
Neon Free currently offers a six-hour instant-restore window; it does not include
scheduled snapshot backups. Decide an independent backup policy before using
this deployment for data that needs longer recovery retention.
