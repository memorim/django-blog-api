import hashlib
import logging

from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.http import HttpResponse

from .apps import current_request


logger = logging.getLogger("blog.requests")
ADMIN_LOGIN_LIMIT = 5
ADMIN_LOGIN_WINDOW = 300


class RequestLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        context_token = current_request.set(request)
        try:
            return self.handle(request)
        finally:
            current_request.reset(context_token)

    def handle(self, request):
        login_key = None
        if request.method == "POST" and request.path == "/admin/login/":
            raw_username = request.POST.get("username", "")
            username = get_user_model().normalize_username(raw_username.strip())
            identity = f"{request.META.get('REMOTE_ADDR', '')}\0{username}"
            login_key = f"admin_login_{hashlib.sha256(identity.encode()).hexdigest()}"
            if cache.get(login_key, 0) >= ADMIN_LOGIN_LIMIT:
                logger.warning("auth action=admin_login_throttled")
                return HttpResponse("Too many login attempts", status=429)

        response = self.get_response(request)

        if login_key:
            if response.status_code in (301, 302, 303):
                cache.delete(login_key)
            elif not cache.add(login_key, 1, ADMIN_LOGIN_WINDOW):
                try:
                    cache.incr(login_key)
                except ValueError:
                    cache.set(login_key, 1, ADMIN_LOGIN_WINDOW)

        level = logging.ERROR if response.status_code >= 500 else logging.WARNING if response.status_code >= 400 else logging.INFO
        logger.log(
            level,
            "http method=%s path=%s status=%s",
            request.method,
            request.path,
            response.status_code,
        )
        return response
