"""Check the real production settings in isolated processes, without a live DB."""
import os
import secrets
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = {
    **{key: value for key, value in os.environ.items()
       if not key.startswith(('DJANGO_', 'POSTGRES_'))},
    'DJANGO_SETTINGS_MODULE': 'blog_project.settings',
    'DJANGO_DEBUG': '0',
    'DJANGO_SECRET_KEY': secrets.token_urlsafe(64),
    'DJANGO_ALLOWED_HOSTS': 'blog.example.test',
    'DJANGO_CSRF_TRUSTED_ORIGINS': 'https://blog.example.test',
    'POSTGRES_DB': 'isolated_configuration_fixture',
    'POSTGRES_USER': 'fixture',
    'POSTGRES_PASSWORD': 'fixture-not-a-real-credential',
    'POSTGRES_HOST': '127.0.0.1',
}


def run(code, changes=None, success=True):
    result = subprocess.run(
        [sys.executable, '-c', code], cwd=ROOT,
        env={**BASE, **(changes or {})}, capture_output=True, text=True,
    )
    if (result.returncode == 0) != success:
        raise AssertionError(result.stdout + result.stderr)


CHECK = '''
import django
django.setup()
from django.core.management import call_command
call_command('check', deploy=True, fail_level='WARNING')
'''
run(CHECK + '''
from django.conf import settings
from django.test import Client
assert not settings.DEBUG
assert settings.DATABASES['default']['ENGINE'] == 'django.db.backends.postgresql'
assert settings.SESSION_COOKIE_SECURE and settings.CSRF_COOKIE_SECURE
assert not settings.API_DOCS_ENABLED
client = Client(HTTP_HOST='blog.example.test')
response = client.get('/api/docs')
assert response.status_code == 301
assert response['Location'] == 'https://blog.example.test/api/docs'
assert client.get('/api/docs', HTTP_X_FORWARDED_PROTO='https').status_code == 301
response = client.get('/api/docs', secure=True)
assert response.status_code == 404
assert 'max-age=31536000' in response['Strict-Transport-Security']
assert response['X-Content-Type-Options'] == 'nosniff'
assert response['X-Frame-Options'] == 'DENY'
assert b'Traceback' not in response.content
assert client.get('/', HTTP_HOST='attacker.example').status_code == 400
''')
run(CHECK + '''
from django.test import Client
response = Client(HTTP_HOST='blog.example.test').get('/api/docs', HTTP_X_FORWARDED_PROTO='https')
assert response.status_code == 404
assert 'Strict-Transport-Security' in response
''', {'DJANGO_TRUST_HTTPS_PROXY': '1'})
run(CHECK + '''
from django.conf import settings
assert settings.DATABASES['default']['OPTIONS'] == {
    'sslmode': 'verify-full', 'sslrootcert': '/etc/ssl/certs/ca-certificates.crt'
}
''', {'POSTGRES_SSLMODE': 'verify-full', 'POSTGRES_SSLROOTCERT': '/etc/ssl/certs/ca-certificates.crt'})
for invalid in [
    {'DJANGO_SECRET_KEY': ''},
    {'DJANGO_SECRET_KEY': 'short'},
    {'DJANGO_ALLOWED_HOSTS': '*'},
    {'POSTGRES_DB': ''},
    {'DJANGO_HTTPS': '0'},
    {'POSTGRES_SSLMODE': 'unsafe-typo'},
]:
    run(CHECK, invalid, success=False)
print('Production settings: HTTPS redirect, HSTS, host boundary, proxy trust and fail-closed checks passed')
