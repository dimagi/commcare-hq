import datetime

from django.test import TestCase

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import (
    CommCareUser,
    DeactivateMobileWorkerTrigger,
)


class TestDeactivateMobileWorkerTrigger(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.date_deactivation = datetime.date(2022, 2, 22)

        cls.domain = create_domain('test-auto-deactivate-001')
        user_normal = CommCareUser.create(
            domain=cls.domain.name,
            username='user_normal',
            password='secret',
            created_by=None,
            created_via=None,
            is_active=True,
        )
        user_deactivate = CommCareUser.create(
            domain=cls.domain.name,
            username='user_deactivate',
            password='secret',
            created_by=None,
            created_via=None,
            is_active=True,
        )
        user_past_deactivate = CommCareUser.create(
            domain=cls.domain.name,
            username='user_past_deactivate',
            password='secret',
            created_by=None,
            created_via=None,
            is_active=True,
        )
        user_future_deactivate = CommCareUser.create(
            domain=cls.domain.name,
            username='user_future_deactivate',
            password='secret',
            created_by=None,
            created_via=None,
            is_active=True,
        )
        cls.users = [
            user_normal,
            user_deactivate,
            user_past_deactivate,
            user_future_deactivate,
        ]

        DeactivateMobileWorkerTrigger.objects.create(
            domain=cls.domain.name,
            user_id=user_deactivate.user_id,
            deactivate_after=cls.date_deactivation
        )
        DeactivateMobileWorkerTrigger.objects.create(
            domain=cls.domain.name,
            user_id=user_future_deactivate.user_id,
            deactivate_after=cls.date_deactivation + datetime.timedelta(days=1)
        )
        DeactivateMobileWorkerTrigger.objects.create(
            domain=cls.domain.name,
            user_id=user_past_deactivate.user_id,
            deactivate_after=cls.date_deactivation - datetime.timedelta(days=1)
        )

    @classmethod
    def tearDownClass(cls):
        DeactivateMobileWorkerTrigger.objects.all().delete()
        for user in cls.users:
            user.delete(user.domain, None)
        cls.domain.delete()
        super().tearDownClass()

    def test_users_deactivated(self):
        active_statuses = [(u.username, u.is_active) for u in self.users]
        self.assertListEqual(
            active_statuses,
            [
                ('user_normal', True),
                ('user_deactivate', True),
                ('user_past_deactivate', True),
                ('user_future_deactivate', True),
            ]
        )
        self.assertEqual(
            DeactivateMobileWorkerTrigger.objects.count(), 3
        )

        DeactivateMobileWorkerTrigger.deactivate_mobile_workers(
            self.domain, self.date_deactivation
        )

        refreshed_users = [CommCareUser.get_by_user_id(u.get_id) for u in self.users]
        new_active_statuses = [(u.username, u.is_active) for u in refreshed_users]
        self.assertListEqual(
            new_active_statuses,
            [
                ('user_normal', True),
                ('user_deactivate', False),
                ('user_past_deactivate', False),
                ('user_future_deactivate', True),
            ]
        )

        self.assertEqual(
            DeactivateMobileWorkerTrigger.objects.count(), 1
        )
