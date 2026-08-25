import logging
from datetime import datetime
from typing import Annotated

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.forms import UserCreationForm
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.http import parse_etags, quote_etag
from ninja import NinjaAPI, Schema
from ninja.errors import HttpError
from ninja.security import APIKeyHeader
from ninja.throttling import AnonRateThrottle, AuthRateThrottle
from pydantic import AfterValidator, ConfigDict, Field, StrictInt

from .models import ApiToken, Article, Category, Comment, hash_token, issue_token


logger = logging.getLogger("blog.api")


def reject_blank(value):
    if not value.strip():
        raise ValueError("Значение не может состоять только из пробельных символов")
    return value


ArticleTitle = Annotated[str, Field(min_length=1, max_length=200), AfterValidator(reject_blank)]
ArticleContent = Annotated[str, Field(min_length=1, max_length=50_000), AfterValidator(reject_blank)]
CommentContent = Annotated[str, Field(min_length=1, max_length=5_000), AfterValidator(reject_blank)]


class StrictSchema(Schema):
    model_config = ConfigDict(extra="forbid")


class CredentialsIn(StrictSchema):
    username: str = Field(min_length=1, max_length=150)
    password: str = Field(min_length=1, max_length=128)


class AuthOut(Schema):
    user_id: int
    username: str
    token: str


class ArticleIn(StrictSchema):
    title: ArticleTitle
    content: ArticleContent
    category_id: StrictInt | None = None


class ArticleOut(ArticleIn):
    id: int
    author_id: int
    created_at: datetime
    updated_at: datetime


class CommentIn(StrictSchema):
    article_id: StrictInt
    content: CommentContent


class CommentUpdate(StrictSchema):
    content: CommentContent


class CommentOut(Schema):
    id: int
    article_id: int
    author_id: int
    content: str
    created_at: datetime
    updated_at: datetime


class HeaderTokenAuth(APIKeyHeader):
    param_name = "X-API-Token"

    def authenticate(self, request, key):
        if not isinstance(key, str) or len(key) != 256 or not key.isascii() or not key.isalnum():
            logger.warning("auth action=token_rejected reason=format")
            return None
        try:
            token = ApiToken.objects.select_related("user").get(
                key_hash=hash_token(key), expires_at__gt=timezone.now(), user__is_active=True
            )
        except ApiToken.DoesNotExist:
            logger.warning("auth action=token_rejected")
            return None
        return token.user


token_auth = HeaderTokenAuth()
login_throttle = AnonRateThrottle("5/m")
register_throttle = AnonRateThrottle("5/m")
write_throttle = AuthRateThrottle("60/m")
api = NinjaAPI(
    title="Blog API",
    version="1.0",
    docs_url="/docs" if settings.API_DOCS_ENABLED else None,
    openapi_url="/openapi.json" if settings.API_DOCS_ENABLED else None,
)


def owned_object(model, object_id, user, *, for_update=False):
    objects = model.objects.select_for_update() if for_update else model.objects
    obj = get_object_or_404(objects, pk=object_id)
    if obj.author_id != user.id:
        logger.warning(
            "permission_denied model=%s object_id=%s user_id=%s",
            model._meta.label_lower,
            object_id,
            user.id,
        )
        raise HttpError(403, "Редактировать или удалять можно только свои объекты")
    return obj


def article_etag(article):
    return quote_etag(f"{article.pk}:{article.updated_at.isoformat()}")


def enforce_if_match(request, article):
    supplied = request.headers.get("If-Match")
    if supplied:
        etags = parse_etags(supplied)
        if "*" not in etags and article_etag(article) not in etags:
            raise HttpError(412, "Статья была изменена другим запросом")


def paginate(queryset, limit, offset):
    if not 1 <= limit <= 100 or not 0 <= offset <= 10_000:
        raise HttpError(400, "limit должен быть от 1 до 100, offset — от 0 до 10000")
    return list(queryset[offset : offset + limit])


@api.post("/auth/register", response={201: AuthOut}, throttle=register_throttle)
@transaction.atomic
def register(request, payload: CredentialsIn):
    form = UserCreationForm(
        {"username": payload.username, "password1": payload.password, "password2": payload.password}
    )
    if not form.is_valid():
        logger.warning("registration_failed fields=%s", ",".join(form.errors))
        raise HttpError(400, "Некорректные регистрационные данные")

    user = form.save()
    token = issue_token(user)
    logger.info("auth action=register user_id=%s", user.id)
    return 201, {"user_id": user.id, "username": user.username, "token": token}


@api.post("/auth/login", response=AuthOut, throttle=login_throttle)
def login(request, payload: CredentialsIn):
    user = authenticate(request, username=payload.username, password=payload.password)
    if user is None:
        logger.warning("auth action=login_failed")
        raise HttpError(401, "Неверные имя пользователя или пароль")

    token = issue_token(user)
    logger.info("auth action=login user_id=%s", user.id)
    return {"user_id": user.id, "username": user.username, "token": token}


@api.post("/auth/logout", auth=token_auth, response={204: None}, throttle=write_throttle)
def logout(request):
    ApiToken.objects.filter(user=request.auth).delete()
    logger.info("auth action=logout user_id=%s", request.auth.id)
    return 204, None


@api.get("/articles", response=list[ArticleOut])
def list_articles(request, limit: int = 20, offset: int = 0):
    return paginate(Article.objects.all(), limit, offset)


@api.post("/articles", auth=token_auth, response={201: ArticleOut}, throttle=write_throttle)
def create_article(request, payload: ArticleIn, response: HttpResponse):
    category = None if payload.category_id is None else get_object_or_404(Category, pk=payload.category_id)
    article = Article.objects.create(
        author=request.auth,
        category=category,
        title=payload.title,
        content=payload.content,
    )
    response["ETag"] = article_etag(article)
    return 201, article


@api.get("/articles/{article_id}", response=ArticleOut)
def get_article(request, article_id: int, response: HttpResponse):
    article = get_object_or_404(Article, pk=article_id)
    response["ETag"] = article_etag(article)
    return article


@api.put("/articles/{article_id}", auth=token_auth, response=ArticleOut, throttle=write_throttle)
@transaction.atomic
def update_article(request, article_id: int, payload: ArticleIn, response: HttpResponse):
    article = owned_object(Article, article_id, request.auth, for_update=True)
    enforce_if_match(request, article)
    article.category = (
        None if payload.category_id is None else get_object_or_404(Category, pk=payload.category_id)
    )
    article.title = payload.title
    article.content = payload.content
    article.save()
    response["ETag"] = article_etag(article)
    return article


@api.delete("/articles/{article_id}", auth=token_auth, response={204: None}, throttle=write_throttle)
@transaction.atomic
def delete_article(request, article_id: int):
    article = owned_object(Article, article_id, request.auth, for_update=True)
    enforce_if_match(request, article)
    if article.comments.exclude(author=request.auth).exists():
        raise HttpError(409, "Нельзя удалить статью с комментариями других пользователей")
    article.delete()
    return 204, None


@api.get("/comments", response=list[CommentOut])
def list_comments(request, article_id: int | None = None, limit: int = 20, offset: int = 0):
    comments = Comment.objects.all()
    if article_id is not None:
        get_object_or_404(Article, pk=article_id)
        comments = comments.filter(article_id=article_id)
    return paginate(comments, limit, offset)


@api.post("/comments", auth=token_auth, response={201: CommentOut}, throttle=write_throttle)
def create_comment(request, payload: CommentIn):
    article = get_object_or_404(Article, pk=payload.article_id)
    return 201, Comment.objects.create(article=article, author=request.auth, content=payload.content)


@api.get("/comments/{comment_id}", response=CommentOut)
def get_comment(request, comment_id: int):
    return get_object_or_404(Comment, pk=comment_id)


@api.put("/comments/{comment_id}", auth=token_auth, response=CommentOut, throttle=write_throttle)
def update_comment(request, comment_id: int, payload: CommentUpdate):
    comment = owned_object(Comment, comment_id, request.auth)
    comment.content = payload.content
    comment.save()
    return comment


@api.delete("/comments/{comment_id}", auth=token_auth, response={204: None}, throttle=write_throttle)
def delete_comment(request, comment_id: int):
    owned_object(Comment, comment_id, request.auth).delete()
    return 204, None
