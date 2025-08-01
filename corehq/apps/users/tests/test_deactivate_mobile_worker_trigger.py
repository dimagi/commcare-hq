import datetime

from django.test import TestCase

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import (
    CommCareUser,
    DeactivateMobileWorkerTrigger,
    DeactivateMobileWorkerTriggerUpdateMessage,
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
        active_statuses = [(u.username, u.is_active_in_domain(self.domain.name)) for u in self.users]
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
        new_active_statuses = [(u.username, u.is_active_in_domain(self.domain.name)) for u in refreshed_users]
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


class UpdateDeactivateMobileWorkerTriggerTest(TestCase):

    def tearDown(self):
        DeactivateMobileWorkerTrigger.objects.all().delete()
        super().tearDown()

    def test_updates(self):
        existing_trigger = DeactivateMobileWorkerTrigger.objects.create(
            domain='test-trigger',
            user_id='user-trigger-001',
            deactivate_after=datetime.date(2022, 2, 1),
        )
        status = DeactivateMobileWorkerTrigger.update_trigger(
            'test-trigger', 'user-trigger-001', datetime.date(2022, 3, 1),
        )
        self.assertEqual(
            status, DeactivateMobileWorkerTriggerUpdateMessage.UPDATED
        )
        existing_trigger.refresh_from_db()
        self.assertEqual(
            existing_trigger.deactivate_after,
            datetime.date(2022, 3, 1)
        )

    def test_creates(self):
        status = DeactivateMobileWorkerTrigger.update_trigger(
            'test-trigger', 'user-trigger-002', datetime.date(2022, 2, 1)
        )
        self.assertEqual(
            status, DeactivateMobileWorkerTriggerUpdateMessage.CREATED
        )
        trigger = DeactivateMobileWorkerTrigger.objects.get(
            domain='test-trigger',
            user_id='user-trigger-002'
        )
        self.assertEqual(
            trigger.deactivate_after,
            datetime.date(2022, 2, 1)
        )

    def test_deletes(self):
        DeactivateMobileWorkerTrigger.objects.create(
            domain='test-trigger',
            user_id='user-trigger-003',
            deactivate_after=datetime.date(2022, 3, 1),
        )
        status = DeactivateMobileWorkerTrigger.update_trigger(
            'test-trigger', 'user-trigger-003', None
        )
        self.assertEqual(
            status, DeactivateMobileWorkerTriggerUpdateMessage.DELETED
        )
        self.assertFalse(
            DeactivateMobileWorkerTrigger.objects.filter(
                domain='test-trigger',
                user_id='user-trigger-003'
            ).exists()
        )

    def test_no_update_needed(self):
        existing_trigger = DeactivateMobileWorkerTrigger.objects.create(
            domain='test-trigger',
            user_id='user-trigger-001',
            deactivate_after=datetime.date(2022, 2, 1),
        )
        status = DeactivateMobileWorkerTrigger.update_trigger(
            'test-trigger', 'user-trigger-001', datetime.date(2022, 2, 1),
        )
        self.assertIsNone(status)
        existing_trigger.refresh_from_db()
        self.assertEqual(
            existing_trigger.deactivate_after,
            datetime.date(2022, 2, 1)
        )

    def test_noop(self):
        status = DeactivateMobileWorkerTrigger.update_trigger(
            'test-trigger', 'user-trigger-004', None
        )
        self.assertIsNone(status)
        self.assertFalse(
            DeactivateMobileWorkerTrigger.objects.filter(
                domain='test-trigger',
                user_id='user-trigger-004'
            ).exists()
        )

    def test_string_value(self):
        status = DeactivateMobileWorkerTrigger.update_trigger(
            'test-trigger', 'user-trigger-005', '03-2022'
        )
        self.assertEqual(
            status, DeactivateMobileWorkerTriggerUpdateMessage.CREATED
        )
        trigger = DeactivateMobileWorkerTrigger.objects.get(
            domain='test-trigger',
            user_id='user-trigger-005'
        )
        self.assertEqual(
            trigger.deactivate_after,
            datetime.date(2022, 3, 1)
        )

    def test_bad_value(self):
        with self.assertRaises(ValueError):
            DeactivateMobileWorkerTrigger.update_trigger(
                'test-trigger', 'user-trigger-006', 'foobar'
            )

    def test_bad_value_date(self):
        with self.assertRaises(ValueError):
            DeactivateMobileWorkerTrigger.update_trigger(
                'test-trigger', 'user-trigger-006', '01-02-2023'
            )

    def test_noop_blank_string(self):
        status = DeactivateMobileWorkerTrigger.update_trigger(
            'test-trigger', 'user-trigger-007', ''
        )

        self.assertIsNone(status)
        self.assertFalse(
            DeactivateMobileWorkerTrigger.objects.filter(
                domain='test-trigger',
                user_id='user-trigger-007'
            ).exists()
        )


class GetDeactivateAfterDateTest(TestCase):

    def tearDown(self):
        DeactivateMobileWorkerTrigger.objects.all().delete()
        super().tearDown()

    def test_no_trigger_exists(self):
        deactivate_after = DeactivateMobileWorkerTrigger.get_deactivate_after_date(
            'test-trigger-date', 'user-trigger-001'
        )
        self.assertIsNone(deactivate_after)

    def test_date_is_fetched(self):
        DeactivateMobileWorkerTrigger.objects.create(
            domain='test-trigger-date',
            user_id='user-trigger-002',
            deactivate_after=datetime.date(2022, 2, 1),
        )
        deactivate_after = DeactivateMobileWorkerTrigger.get_deactivate_after_date(
            'test-trigger-date', 'user-trigger-002'
        )
        self.assertEqual(
            deactivate_after, datetime.date(2022, 2, 1)
        )
