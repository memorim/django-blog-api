from django.test import TestCase
from blog.throttling import consume_budget
from blog.models import RequestBudget


class SharedBudgetTests(TestCase):
    def test_budget_persists_across_callers_and_expires(self):
        self.assertTrue(consume_budget('login:a', 2, 60, now=1000)[0])
        self.assertTrue(consume_budget('login:a', 2, 60, now=1001)[0])
        self.assertFalse(consume_budget('login:a', 2, 60, now=1002)[0])
        self.assertEqual(RequestBudget.objects.get().count, 3)
        self.assertTrue(consume_budget('login:a', 2, 60, now=1060)[0])
        self.assertTrue(consume_budget('login:b', 2, 60, now=1002)[0])
