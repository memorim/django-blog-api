"""Real row-lock checks; SQLite cannot provide SELECT FOR UPDATE semantics."""
import importlib
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection, connections, close_old_connections
from django.test import Client, TransactionTestCase

from blog.models import Article, issue_token


@skipUnless(connection.vendor == "postgresql", "PostgreSQL is required for row-lock concurrency checks")
class PostgresArticleConcurrencyTests(TransactionTestCase):
    def setUp(self):
        cache.clear()
        self.owner = get_user_model().objects.create_user(username="pg-owner", password="Fixture-passphrase-2026!")
        self.token = issue_token(self.owner)
        self.article = Article.objects.create(author=self.owner, title="Original", content="Original content")
        self.path = f"/api/articles/{self.article.pk}"
        self.etag = Client().get(self.path).headers["ETag"]

    def race(self, operations):
        api = importlib.import_module("blog.api")
        original = api.owned_object
        gate = Barrier(2, timeout=10)

        def before_lock(*args, **kwargs):
            if kwargs.get("for_update"):
                gate.wait()
            return original(*args, **kwargs)

        def mutate(operation):
            close_old_connections()
            try:
                client = Client()
                headers = {"HTTP_X_API_TOKEN": self.token, "HTTP_IF_MATCH": self.etag}
                if operation == "delete":
                    result = client.delete(self.path, **headers)
                else:
                    result = client.put(self.path, data=json.dumps({"title": operation, "content": "Updated content", "category_id": None}), content_type="application/json", **headers)
                return operation, result.status_code
            finally:
                connections.close_all()

        with patch.object(api, "owned_object", before_lock), ThreadPoolExecutor(max_workers=2) as workers:
            return list(workers.map(mutate, operations))

    def test_two_updates_with_one_etag_cannot_silently_overwrite(self):
        results = self.race(["First revision", "Second revision"])
        self.assertEqual(sorted(code for _, code in results), [200, 412])
        self.article.refresh_from_db()
        self.assertEqual(self.article.title, next(title for title, code in results if code == 200))
        self.assertNotEqual(Client().get(self.path).headers["ETag"], self.etag)

    def test_delete_and_update_respect_the_same_precondition(self):
        results = dict(self.race(["Updated revision", "delete"]))
        if results["delete"] == 204:
            self.assertEqual(results["Updated revision"], 404)
            self.assertFalse(Article.objects.filter(pk=self.article.pk).exists())
        else:
            self.assertEqual(results, {"Updated revision": 200, "delete": 412})
            self.article.refresh_from_db()
            self.assertEqual(self.article.title, "Updated revision")
