import logging
from contextvars import ContextVar

from django.apps import AppConfig


logger = logging.getLogger("blog.audit")
current_request = ContextVar("blog_current_request", default=None)


def current_user_id():
    request = current_request.get()
    if request is None:
        return None
    user = getattr(request, "auth", None) or getattr(request, "user", None)
    return getattr(user, "pk", None)


def log_save(sender, instance, created, raw=False, **kwargs):
    if not raw:
        logger.info(
            "crud model=%s action=%s object_id=%s user_id=%s",
            sender._meta.label_lower,
            "created" if created else "updated",
            instance.pk,
            current_user_id(),
        )


def log_delete(sender, instance, **kwargs):
    logger.info(
        "crud model=%s action=deleted object_id=%s user_id=%s",
        sender._meta.label_lower,
        instance.pk,
        current_user_id(),
    )


def detect_password_change(sender, instance, raw=False, **kwargs):
    instance._blog_password_changed = False
    if not raw and instance.pk:
        previous = sender.objects.filter(pk=instance.pk).values_list("password", flat=True).first()
        instance._blog_password_changed = previous is not None and previous != instance.password


def revoke_token_after_password_change(sender, instance, **kwargs):
    if getattr(instance, "_blog_password_changed", False):
        from .models import ApiToken

        ApiToken.objects.filter(user_id=instance.pk).delete()


def log_user_login(sender, user, **kwargs):
    logger.info("auth action=login user_id=%s", user.pk)


def log_user_logout(sender, user, **kwargs):
    logger.info("auth action=logout user_id=%s", getattr(user, "pk", None))


def log_user_login_failed(sender, credentials, **kwargs):
    logger.warning("auth action=login_failed")


class BlogConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "blog"

    def ready(self):
        from django.contrib.auth import get_user_model
        from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
        from django.db.models.signals import post_delete, post_save, pre_save

        from .models import Article, Comment

        user_model = get_user_model()
        for model in (user_model, Article, Comment):
            label = model._meta.label_lower
            post_save.connect(log_save, sender=model, dispatch_uid=f"blog.audit.save.{label}")
            post_delete.connect(log_delete, sender=model, dispatch_uid=f"blog.audit.delete.{label}")

        pre_save.connect(
            detect_password_change,
            sender=user_model,
            dispatch_uid="blog.auth.detect_password_change",
        )
        post_save.connect(
            revoke_token_after_password_change,
            sender=user_model,
            dispatch_uid="blog.auth.revoke_token_after_password_change",
        )

        user_logged_in.connect(log_user_login, dispatch_uid="blog.audit.login")
        user_logged_out.connect(log_user_logout, dispatch_uid="blog.audit.logout")
        user_login_failed.connect(log_user_login_failed, dispatch_uid="blog.audit.login_failed")
