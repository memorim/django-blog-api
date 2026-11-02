"""Atomic shared fixed-window limits, backed by the application's SQL database."""
import hashlib
import time

from django.db import connection
from ninja.throttling import BaseThrottle


def consume_budget(identity, maximum, duration, now=None):
    now = time.time() if now is None else now
    key = hashlib.sha256(identity.encode()).hexdigest()
    with connection.cursor() as cursor:
        cursor.execute('DELETE FROM blog_requestbudget WHERE reset_at < %s', [now - 3600])
        cursor.execute('''INSERT INTO blog_requestbudget (key, count, reset_at) VALUES (%s, 1, %s)
            ON CONFLICT(key) DO UPDATE SET
            count = CASE WHEN blog_requestbudget.reset_at <= %s THEN 1
                         WHEN blog_requestbudget.count < %s THEN blog_requestbudget.count + 1
                         ELSE blog_requestbudget.count END,
            reset_at = CASE WHEN blog_requestbudget.reset_at <= %s THEN EXCLUDED.reset_at
                            ELSE blog_requestbudget.reset_at END
            RETURNING count, reset_at''', [key, now + duration, now, maximum + 1, now])
        count, reset = cursor.fetchone()
    return count <= maximum, max(1, reset - now)


class DatabaseThrottle(BaseThrottle):
    def __init__(self, scope, maximum, duration=60):
        self.scope, self.maximum, self.duration = scope, maximum, duration

    def allow_request(self, request):
        user = getattr(request, 'auth', None)
        identity = f'user:{user.pk}' if user else f'ip:{self.get_ident(request)}'
        allowed, _ = consume_budget(f'{self.scope}:{identity}', self.maximum, self.duration)
        return allowed

    def wait(self):
        return self.duration
