import re

from datetime import datetime
from unittest.mock import patch

from django.test import TestCase

from corehq.apps.commtrack.tests.util import make_loc
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.custom_data_fields.models import (
    CustomDataFieldsDefinition,
    CustomDataFieldsProfile,
    Field,
    PROFILE_SLUG,
)
from corehq.apps.locations.tests.util import delete_all_locations
from corehq.apps.users.views.mobile.custom_data_fields import UserFieldsView
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.bulk_download import parse_mobile_users


@patch('corehq.apps.users.bulk_download.domain_has_privilege', lambda x, y: True)
class TestDownloadMobileWorkers(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.domain = 'bookshelf'
        cls.other_domain = 'book'
        cls.domain_obj = create_domain(cls.domain)
        cls.other_domain_obj = create_domain(cls.other_domain)
        cls.location = make_loc('1', 'loc1', cls.domain)
        cls.other_location = make_loc('2', 'loc2', cls.other_domain)

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
            phone_number='27786541239',
            user_data={'born': 1862}
        )
        cls.user1.set_location(cls.location)
        cls.user2 = CommCareUser.create(
            cls.domain_obj.name,
            'george',
            'anotherbadpassword',
            None,
            None,
            first_name='George',
            last_name='Eliot',
            user_data={'born': 1849, PROFILE_SLUG: cls.profile.id},
        )
        cls.user2.set_location(cls.location)
        cls.user3 = CommCareUser.create(
            cls.other_domain_obj.name,
            'emily',
            'anothersuperbadpassword',
            None,
            None,
            first_name='Emily',
            last_name='Bronte',
        )
        cls.user3.set_location(cls.other_location)

    @classmethod
    def tearDownClass(cls):
        cls.user1.delete(cls.domain_obj.name, deleted_by=None)
        cls.user2.delete(cls.domain_obj.name, deleted_by=None)
        cls.user3.delete(cls.other_domain_obj.name, deleted_by=None)
        cls.domain_obj.delete()
        cls.other_domain_obj.delete()
        cls.definition.delete()
        delete_all_locations()
        super().tearDownClass()

    def test_download(self):
        # Add multiple phone numbers to user1
        self.__class__.user1.add_phone_number('27786544321')
        self.__class__.user1.save()

        (headers, rows) = parse_mobile_users(self.domain_obj.name, {})

        rows = list(rows)
        self.assertEqual(2, len(rows))
        self.assertTrue('phone-number 1' in headers)
        self.assertTrue('phone-number 2' in headers)

        spec = dict(zip(headers, rows[0]))
        self.assertEqual('edith', spec['username'])
        self.assertTrue(re.search(r'^\*+$', spec['password']))
        self.assertEqual('True', spec['is_active'])
        self.assertEqual('Edith Wharton', spec['name'])
        self.assertTrue(spec['registered_on (read only)'].startswith(datetime.today().strftime("%Y-%m-%d")))
        self.assertEqual('', spec['data: _type'])
        self.assertEqual(1862, spec['data: born'])
        self.assertEqual('1', spec['location_code 1'])
        self.assertEqual(spec['phone-number 1'], '27786541239')
        self.assertEqual(spec['phone-number 2'], '27786544321')

    def test_multiple_domain_download(self):
        (headers, rows) = parse_mobile_users(self.domain_obj.name, {'domains': ['bookshelf', 'book']})

        rows = list(rows)
        self.assertEqual(3, len(rows))
        spec = dict(zip(headers, rows[2]))
        self.assertEqual('emily', spec['username'])
        self.assertEqual('True', spec['is_active'])
        self.assertEqual('Emily Bronte', spec['name'])
        self.assertEqual('2', spec['location_code 1'])
