import hashlib
import logging

from .throttling import consume_budget
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
            allowed, retry_after = consume_budget(login_key, ADMIN_LOGIN_LIMIT, ADMIN_LOGIN_WINDOW)
            if not allowed:
                logger.warning("auth action=admin_login_throttled")
                return HttpResponse("Too many login attempts", status=429, headers={"Retry-After": str(int(retry_after))})

        response = self.get_response(request)

        if login_key and response.status_code in (301, 302, 303):
            from .models import RequestBudget
            RequestBudget.objects.filter(key=hashlib.sha256(login_key.encode()).hexdigest()).delete()

        level = logging.ERROR if response.status_code >= 500 else logging.WARNING if response.status_code >= 400 else logging.INFO
        logger.log(
            level,
            "http method=%s path=%s status=%s",
            request.method,
            request.path,
            response.status_code,
        )
        return response
