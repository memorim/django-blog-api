import json

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase

from blog.models import Article, Category, Comment, issue_token


class AdversarialBlogApiTests(TestCase):
    password = "S3cure-passphrase!"

    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.owner = user_model.objects.create_user(username="attack-owner", password=cls.password)
        cls.other = user_model.objects.create_user(username="attack-other", password=cls.password)
        cls.admin = user_model.objects.create_superuser(username="attack-admin", password=cls.password)
        cls.owner_token = issue_token(cls.owner)
        cls.other_token = issue_token(cls.other)
        cls.category = Category.objects.create( name="Adversarial", slug="adversarial")
        cls.article = Article.objects.create(
            author=cls.owner,
            category=cls.category,
            title="Original title",
            content="Original content",
        )

    def setUp(self):
        cache.clear()
        self.client = Client()

    def post(self, path, payload=None, token=None):
        headers = {"HTTP_X_API_TOKEN": token} if token is not None else {}
        return self.client.post(
            path,
            data=json.dumps(payload or {}),
            content_type="application/json",
            **headers,
        )

    def put(self, path, payload, token, **headers):
        return self.client.put(
            path,
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_API_TOKEN=token,
            **headers,
        )

    def test_non_ascii_token_must_not_crash_authentication(self):
        self.client.raise_request_exception = False

        response = self.post(
            "/api/articles",
            {"title": "Attack", "content": "Attack"},
            "é" * 256,
        )

        self.assertNotEqual(response.status_code, 500)

    def test_admin_login_limit_must_survive_username_whitespace_normalization(self):
        normalized_login = Client().post(
            "/admin/login/",
            {"username": f" {self.admin.username} ", "password": self.password},
        )
        self.assertEqual(normalized_login.status_code, 302)

        for _ in range(5):
            response = self.client.post(
                "/admin/login/",
                {"username": self.admin.username, "password": "wrong-password"},
            )
            self.assertEqual(response.status_code, 200)

        bypass = self.client.post(
            "/admin/login/",
            {"username": f" {self.admin.username} ", "password": "wrong-password"},
        )

        self.assertEqual(bypass.status_code, 429)

    def test_password_change_must_revoke_existing_api_token(self):
        self.owner.set_password("N3w-secure-passphrase!")
        self.owner.save(update_fields=["password"])

        response = self.post(
            "/api/articles",
            {"title": "Still authenticated", "content": "Old token survived"},
            self.owner_token,
        )

        self.assertEqual(response.status_code, 401)

    def test_whitespace_only_article_must_be_rejected(self):
        response = self.post(
            "/api/articles",
            {"title": "   ", "content": "\t\n"},
            self.owner_token,
        )

        self.assertEqual(response.status_code, 422)

    def test_boolean_article_id_must_not_select_article_one(self):
        response = self.post(
            "/api/comments",
            {"article_id": True, "content": "Attached through boolean coercion"},
            self.other_token,
        )

        self.assertEqual(response.status_code, 422)
        self.assertFalse(Comment.objects.filter(content="Attached through boolean coercion").exists())

    def test_deleting_article_must_not_delete_another_users_comment(self):
        foreign_comment = Comment.objects.create(
            article=self.article,
            author=self.other,
            content="Another user's data",
        )

        response = self.client.delete(
            f"/api/articles/{self.article.id}",
            HTTP_X_API_TOKEN=self.owner_token,
        )

        self.assertEqual(response.status_code, 409)
        self.assertTrue(Article.objects.filter(pk=self.article.pk).exists())
        self.assertTrue(Comment.objects.filter(pk=foreign_comment.pk).exists())

    def test_stale_if_match_must_not_overwrite_a_newer_article(self):
        first = self.put(
            f"/api/articles/{self.article.id}",
            {"title": "Newer", "content": "Newer version", "category_id": None},
            self.owner_token,
        )
        self.assertEqual(first.status_code, 200)

        stale = self.put(
            f"/api/articles/{self.article.id}",
            {"title": "Stale", "content": "Stale version", "category_id": None},
            self.owner_token,
            HTTP_IF_MATCH='"stale-version"',
        )

        self.assertEqual(stale.status_code, 412)
        self.article.refresh_from_db()
        self.assertEqual(self.article.title, "Newer")

    def test_current_etag_allows_article_update(self):
        detail = self.client.get(f"/api/articles/{self.article.id}")

        response = self.put(
            f"/api/articles/{self.article.id}",
            {"title": "Current", "content": "Current version", "category_id": None},
            self.owner_token,
            HTTP_IF_MATCH=detail.headers["ETag"],
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("ETag", response.headers)

    def test_article_create_must_emit_a_domain_audit_event(self):
        with self.assertLogs("blog", level="INFO") as captured:
            response = self.post(
                "/api/articles",
                {"title": "Audited", "content": "Audit me"},
                self.owner_token,
            )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            any(
                "crud" in message
                and "create" in message
                and f"user_id={self.owner.id}" in message
                for message in captured.output
            ),
            captured.output,
        )
