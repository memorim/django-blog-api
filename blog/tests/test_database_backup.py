import io
from unittest.mock import patch

from django.contrib.auth.models import Group, Permission, User
from django.core.management import call_command
from django.test import TransactionTestCase

from blog.models import Article, Category, Comment, RequestBudget, issue_token
from scripts.database_backup import canonical_dump, verified_url


class LogicalBackupTests(TransactionTestCase):
    def test_restore_preserves_related_data_and_permissions(self):
        author = User.objects.create_user('backup-author', password='fixture-only-password')
        group = Group.objects.create(name='editors')
        permission = Permission.objects.get(codename='change_article')
        group.permissions.add(permission)
        author.groups.add(group)
        category = Category.objects.create(name='Backup category', slug='backup-category')
        article = Article.objects.create(author=author, category=category, title='Backup', content='Round trip')
        Comment.objects.create(author=author, article=article, content='Related comment')
        RequestBudget.objects.create(key='fixture-budget', count=3, reset_at=2000000000)
        issue_token(author)
        original, counts = canonical_dump()
        call_command('flush', interactive=False, verbosity=0)
        with patch('sys.stdin', io.StringIO(original.decode())):
            call_command('loaddata', '-', format='json', verbosity=0)
        restored, restored_counts = canonical_dump()
        self.assertEqual(original, restored)
        self.assertEqual(counts, restored_counts)
        user = User.objects.get(username='backup-author')
        self.assertTrue(user.has_perm('blog.change_article'))
        self.assertEqual(Comment.objects.get().article.author_id, user.pk)
        self.assertEqual(RequestBudget.objects.get().count, 3)
        self.assertTrue(user.check_password('fixture-only-password'))

    def test_remote_backup_connections_require_verified_tls(self):
        url = verified_url('postgresql://fixture:fixture@db.example/backup?sslmode=disable')
        self.assertIn('sslmode=verify-full', url)
        self.assertIn('sslrootcert=system', url)
        with self.assertRaises(ValueError):
            verified_url('https://db.example/backup')
