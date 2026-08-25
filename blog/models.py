import hashlib
import secrets
import string
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


TOKEN_ALPHABET = string.ascii_letters + string.digits


def generate_token():
    return "".join(secrets.choice(TOKEN_ALPHABET) for _ in range(256))


def hash_token(token):
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def token_expiry():
    return timezone.now() + timedelta(days=30)


class ApiToken(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="api_token")
    key_hash = models.CharField(max_length=64, unique=True, editable=False)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    expires_at = models.DateTimeField(default=token_expiry, editable=False)


def issue_token(user):
    token = generate_token()
    now = timezone.now()
    ApiToken.objects.update_or_create(
        user=user,
        defaults={"key_hash": hash_token(token), "created_at": now, "expires_at": now + timedelta(days=30)},
    )
    return token


class Category(models.Model):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True)

    class Meta:
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class Article(models.Model):
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="articles")
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="articles")
    title = models.CharField(max_length=200)
    content = models.TextField(max_length=50_000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class Comment(models.Model):
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="comments")
    content = models.TextField(max_length=5_000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return self.content[:50]
