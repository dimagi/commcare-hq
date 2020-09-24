import re

from datetime import datetime

from django.test import TestCase

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.custom_data_fields.models import (
    CustomDataFieldsDefinition,
    CustomDataFieldsProfile,
    Field,
    PROFILE_SLUG,
)
from corehq.apps.users.views.mobile.custom_data_fields import UserFieldsView
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.bulk_download import parse_users
from corehq.apps.user_importer.importer import GroupMemoizer
from corehq.apps.accounting.models import SoftwarePlanEdition
from corehq.apps.accounting.tests.utils import DomainSubscriptionMixin


class TestDownloadMobileWorkers(TestCase, DomainSubscriptionMixin):
    domain = 'bookshelf'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(cls.domain)

        # APP_USER_PROFILES is on ENTERPRISE and above
        cls.setup_subscription(cls.domain, SoftwarePlanEdition.ADVANCED)

        cls.group_memoizer = GroupMemoizer(domain=cls.domain_obj.name)
        cls.group_memoizer.load_all()

        cls.definition = CustomDataFieldsDefinition(domain=cls.domain_obj.name,
                                                    field_type=UserFieldsView.field_type)
        cls.definition.save()
        cls.definition.set_fields([
            Field(
                slug='born',
                label='Year of Birth',
            ),
            Field(
                slug='_type',
                label='Type',
                choices=['fiction', 'non-fiction'],
            ),
        ])
        cls.definition.save()

        cls.profile = CustomDataFieldsProfile(
            name='Novelist',
            fields={'_type': 'fiction'},
            definition=cls.definition,
        )
        cls.profile.save()

        cls.user1 = CommCareUser.create(
            cls.domain_obj.name,
            'edith',
            'badpassword',
            None,
            None,
            first_name='Edith',
            last_name='Wharton',
            metadata={'born': 1862}
        )
        cls.user2 = CommCareUser.create(
            cls.domain_obj.name,
            'george',
            'anotherbadpassword',
            None,
            None,
            first_name='George',
            last_name='Eliot',
            metadata={'born': 1849, PROFILE_SLUG: cls.profile.id},
        )

    @classmethod
    def tearDownClass(cls):
        cls.user1.delete(deleted_by=None)
        cls.user2.delete(deleted_by=None)
        cls.domain_obj.delete()
        cls.definition.delete()
        cls.teardown_subscriptions()
        super().tearDownClass()

    def test_download(self):
        (headers, rows) = parse_users(self.group_memoizer, self.domain_obj.name, {})
        self.assertNotIn('user_profile', headers)

        rows = list(rows)
        self.assertEqual(2, len(rows))

        spec = dict(zip(headers, rows[0]))
        self.assertEqual('edith', spec['username'])
        self.assertTrue(re.search(r'^\*+$', spec['password']))
        self.assertEqual('True', spec['is_active'])
        self.assertEqual('Edith Wharton', spec['name'])
        self.assertTrue(spec['registered_on (read only)'].startswith(datetime.today().strftime("%Y-%m-%d")))
        self.assertEqual('', spec['data: _type'])
        self.assertEqual(1862, spec['data: born'])

    def test_download_with_profile(self):
        # APP_USER_PROFILES is on ENTERPRISE and above
        self.setup_subscription(self.domain, SoftwarePlanEdition.ENTERPRISE)
        (headers, rows) = parse_users(self.group_memoizer, self.domain_obj.name, {})
        self.assertIn('user_profile', headers)
        self.assertIn('data: _type', headers)

        rows = list(rows)
        self.assertEqual(2, len(rows))

        spec = dict(zip(headers, rows[0]))
        self.assertEqual('edith', spec['username'])
        self.assertEquals('', spec['user_profile'])
        self.assertEqual('', spec['data: _type'])
        self.assertEqual(1862, spec['data: born'])

        spec = dict(zip(headers, rows[1]))
        self.assertEqual('george', spec['username'])
        self.assertEqual('Novelist', spec['user_profile'])
        self.assertEqual('fiction', spec['data: _type'])
        self.assertEqual(1849, spec['data: born'])
