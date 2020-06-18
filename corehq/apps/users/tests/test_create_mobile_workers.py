from django.contrib.auth.models import User
from django.test import TestCase

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import CommCareUser


class TestCreateMobileWorkers(TestCase):
    domain = 'test_create_mobile_workers'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project = create_domain(cls.domain)

    @classmethod
    def tearDownClass(cls):
        cls.project.delete()
        super().tearDownClass()

    def test_create_basic(self):
        user = CommCareUser.create(
            self.domain,
            'mw1',
            's3cr4t',
            None,
            None,
            email='mw1@example.com',
            device_id='my-pixel',
            first_name='Mobile',
            last_name='Worker',
        )
        self.addCleanup(user.delete)
        self.assertEqual(self.domain, user.domain)
        self.assertEqual('mw1', user.username)
        self.assertEqual('mw1@example.com', user.email)
        self.assertEqual(['my-pixel'], user.device_ids)
        self.assertEqual('Mobile', user.first_name)
        self.assertEqual(True, user.is_active)
        self.assertEqual(True, user.is_account_confirmed)

        # confirm user was created / can be accessed
        self.assertIsNotNone(CommCareUser.get_by_username('mw1'))
        self.assertEqual(1, User.objects.filter(username='mw1').count())

        # confirm user can login
        self.assertEqual(True, self.client.login(username='mw1', password='s3cr4t'))

    def test_create_unconfirmed(self):
        user = CommCareUser.create(
            self.domain,
            'mw1',
            's3cr4t',
            None,
            None,
            email='mw1@example.com',
            is_account_confirmed=False,
        )
        self.addCleanup(user.delete)
        self.assertEqual(False, user.is_active)
        self.assertEqual(False, user.is_account_confirmed)
        # confirm user can't login

        django_user = user.get_django_user()
        self.assertEqual(False, django_user.is_active)
        self.assertEqual(False, self.client.login(username='mw1', password='s3cr4t'))

    def test_disallow_unconfirmed_active(self):
        with self.assertRaises(AssertionError):
            CommCareUser.create(
                self.domain,
                'mw1',
                's3cr4t',
                None,
                None,
                email='mw1@example.com',
                is_active=True,
                is_account_confirmed=False,
            )
        # confirm no users were created
        self.assertIsNone(CommCareUser.get_by_username('mw1'))
        self.assertEqual(0, User.objects.filter(username='mw1').count())
