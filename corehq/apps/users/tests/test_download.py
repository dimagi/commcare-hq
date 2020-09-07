import re

from datetime import datetime

from django.test import TestCase

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.bulk_download import parse_users
from corehq.apps.user_importer.importer import GroupMemoizer


class TestDownloadMobileWorkers(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain('bookshelf')

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()
        super().tearDownClass()

    def test_download(self):
        user = CommCareUser.create(
            self.domain_obj.name,
            'edith',
            'badpassword',
            None,
            None,
            first_name='Edith',
            last_name='Wharton',
        )
        self.addCleanup(user.delete, deleted_by=None)
        group_memoizer = GroupMemoizer(domain=self.domain_obj.name)
        group_memoizer.load_all()
        (headers, rows) = parse_users(group_memoizer, self.domain_obj.name, {})
        rows = list(rows)
        self.assertEqual(1, len(rows))
        spec = dict(zip(headers, rows[0]))
        self.assertEqual('edith', spec['username'])
        self.assertTrue(re.search(r'^\*+$', spec['password']))
        self.assertEqual('True', spec['is_active'])
        self.assertEqual('Edith Wharton', spec['name'])
        self.assertTrue(spec['registered_on (read only)'].startswith(datetime.today().strftime("%Y-%m-%d")))
