import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase
from django.utils import timezone

from blog.models import ApiToken, Article, Category, Comment, hash_token, issue_token


class BlogApiTests(TestCase):
    password = "S3cure-passphrase!"

    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.owner = user_model.objects.create_user(username="owner", password=cls.password)
        cls.other = user_model.objects.create_user(username="other", password=cls.password)
        cls.owner_token = issue_token(cls.owner)
        cls.other_token = issue_token(cls.other)
        cls.category = Category.objects.create(name="Django", slug="django")
        cls.article = Article.objects.create(
            author=cls.owner,
            category=cls.category,
            title="Первая статья",
            content="Текст статьи",
        )
        cls.comment = Comment.objects.create(article=cls.article, author=cls.owner, content="Первый комментарий")

    def setUp(self):
        cache.clear()
        self.client = Client()

    def post(self, path, payload=None, token=None):
        headers = {"HTTP_X_API_TOKEN": token} if token else {}
        return self.client.post(path, data=json.dumps(payload or {}), content_type="application/json", **headers)

    def put(self, path, payload, token):
        return self.client.put(
            path,
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_API_TOKEN=token,
        )

    def test_register_success(self):
        response = self.post("/api/auth/register", {"username": "new-user", "password": self.password})

        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(response.json()["token"]), 256)
        self.assertTrue(get_user_model().objects.get(username="new-user").check_password(self.password))
        stored = ApiToken.objects.get(user__username="new-user")
        self.assertEqual(stored.key_hash, hash_token(response.json()["token"]))
        self.assertNotEqual(stored.key_hash, response.json()["token"])

    def test_register_duplicate_fails(self):
        response = self.post("/api/auth/register", {"username": "owner", "password": self.password})

        self.assertEqual(response.status_code, 400)

    def test_login_success(self):
        response = self.post("/api/auth/login", {"username": "owner", "password": self.password})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["token"]), 256)

    def test_login_wrong_password_fails(self):
        response = self.post("/api/auth/login", {"username": "owner", "password": "wrong-password"})

        self.assertEqual(response.status_code, 401)

    def test_logout_success(self):
        response = self.post("/api/auth/logout", token=self.owner_token)

        self.assertEqual(response.status_code, 204)
        self.assertFalse(ApiToken.objects.filter(user=self.owner).exists())

    def test_logout_without_token_fails(self):
        response = self.post("/api/auth/logout")

        self.assertEqual(response.status_code, 401)

    def test_article_list_success(self):
        response = self.client.get("/api/articles")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["id"], self.article.id)

    def test_article_list_invalid_pagination_fails(self):
        response = self.client.get("/api/articles?limit=0")

        self.assertEqual(response.status_code, 400)

    def test_article_create_success(self):
        response = self.post(
            "/api/articles",
            {"title": "Новая", "content": "Содержимое", "category_id": self.category.id},
            self.owner_token,
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Article.objects.get(title="Новая").author, self.owner)

    def test_article_create_without_token_fails(self):
        response = self.post("/api/articles", {"title": "Новая", "content": "Содержимое"})

        self.assertEqual(response.status_code, 401)

    def test_article_detail_success(self):
        response = self.client.get(f"/api/articles/{self.article.id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["title"], self.article.title)

    def test_article_detail_missing_fails(self):
        response = self.client.get("/api/articles/999999")

        self.assertEqual(response.status_code, 404)

    def test_article_update_success(self):
        response = self.put(
            f"/api/articles/{self.article.id}",
            {"title": "Изменена", "content": "Новый текст", "category_id": None},
            self.owner_token,
        )

        self.assertEqual(response.status_code, 200)
        self.article.refresh_from_db()
        self.assertEqual(self.article.title, "Изменена")

    def test_article_update_by_other_user_fails(self):
        response = self.put(
            f"/api/articles/{self.article.id}",
            {"title": "Чужая", "content": "Новый текст", "category_id": None},
            self.other_token,
        )

        self.assertEqual(response.status_code, 403)

    def test_article_delete_success(self):
        response = self.client.delete(
            f"/api/articles/{self.article.id}", HTTP_X_API_TOKEN=self.owner_token
        )

        self.assertEqual(response.status_code, 204)
        self.assertFalse(Article.objects.filter(pk=self.article.id).exists())

    def test_article_delete_by_other_user_fails(self):
        response = self.client.delete(
            f"/api/articles/{self.article.id}", HTTP_X_API_TOKEN=self.other_token
        )

        self.assertEqual(response.status_code, 403)

    def test_comment_list_success(self):
        response = self.client.get(f"/api/comments?article_id={self.article.id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["id"], self.comment.id)

    def test_comment_list_missing_article_fails(self):
        response = self.client.get("/api/comments?article_id=999999")

        self.assertEqual(response.status_code, 404)

    def test_comment_create_success(self):
        response = self.post(
            "/api/comments",
            {"article_id": self.article.id, "content": "Новый комментарий"},
            self.other_token,
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Comment.objects.get(content="Новый комментарий").author, self.other)

    def test_comment_create_without_token_fails(self):
        response = self.post(
            "/api/comments", {"article_id": self.article.id, "content": "Новый комментарий"}
        )

        self.assertEqual(response.status_code, 401)

    def test_comment_detail_success(self):
        response = self.client.get(f"/api/comments/{self.comment.id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["content"], self.comment.content)

    def test_comment_detail_missing_fails(self):
        response = self.client.get("/api/comments/999999")

        self.assertEqual(response.status_code, 404)

    def test_comment_update_success(self):
        response = self.put(
            f"/api/comments/{self.comment.id}", {"content": "Изменённый комментарий"}, self.owner_token
        )

        self.assertEqual(response.status_code, 200)
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.content, "Изменённый комментарий")

    def test_comment_update_by_other_user_fails(self):
        response = self.put(
            f"/api/comments/{self.comment.id}", {"content": "Чужое изменение"}, self.other_token
        )

        self.assertEqual(response.status_code, 403)

    def test_comment_delete_success(self):
        response = self.client.delete(
            f"/api/comments/{self.comment.id}", HTTP_X_API_TOKEN=self.owner_token
        )

        self.assertEqual(response.status_code, 204)
        self.assertFalse(Comment.objects.filter(pk=self.comment.id).exists())

    def test_comment_delete_by_other_user_fails(self):
        response = self.client.delete(
            f"/api/comments/{self.comment.id}", HTTP_X_API_TOKEN=self.other_token
        )

        self.assertEqual(response.status_code, 403)

    def test_expired_token_is_rejected(self):
        ApiToken.objects.filter(user=self.owner).update(expires_at=timezone.now() - timedelta(seconds=1))

        response = self.post("/api/articles", {"title": "Новая", "content": "Текст"}, self.owner_token)

        self.assertEqual(response.status_code, 401)

    def test_login_rotates_previous_token(self):
        response = self.post("/api/auth/login", {"username": "owner", "password": self.password})
        new_token = response.json()["token"]

        old_response = self.post("/api/articles", {"title": "Новая", "content": "Текст"}, self.owner_token)
        new_response = self.post("/api/articles", {"title": "Новая", "content": "Текст"}, new_token)

        self.assertEqual(old_response.status_code, 401)
        self.assertEqual(new_response.status_code, 201)

    def test_login_is_rate_limited(self):
        for _ in range(5):
            response = self.post("/api/auth/login", {"username": "owner", "password": "wrong-password"})
            self.assertEqual(response.status_code, 401)

        response = self.post("/api/auth/login", {"username": "owner", "password": "wrong-password"})

        self.assertEqual(response.status_code, 429)

    def test_admin_login_is_rate_limited(self):
        for _ in range(5):
            response = self.client.post("/admin/login/", {"username": "owner", "password": "wrong-password"})
            self.assertEqual(response.status_code, 200)

        response = self.client.post("/admin/login/", {"username": "owner", "password": "wrong-password"})

        self.assertEqual(response.status_code, 429)

    def test_mass_assignment_is_rejected(self):
        response = self.post(
            "/api/articles",
            {"title": "Новая", "content": "Текст", "author_id": self.other.id},
            self.owner_token,
        )

        self.assertEqual(response.status_code, 422)

    def test_oversized_comment_is_rejected(self):
        response = self.post(
            "/api/comments",
            {"article_id": self.article.id, "content": "x" * 5_001},
            self.owner_token,
        )

        self.assertEqual(response.status_code, 422)

    def test_comment_list_invalid_pagination_fails(self):
        response = self.client.get("/api/comments?limit=0")

        self.assertEqual(response.status_code, 400)

    def test_sql_injection_login_payload_fails(self):
        response = self.post(
            "/api/auth/login",
            {"username": "owner' OR 1=1--", "password": "irrelevant-password"},
        )

        self.assertEqual(response.status_code, 401)
