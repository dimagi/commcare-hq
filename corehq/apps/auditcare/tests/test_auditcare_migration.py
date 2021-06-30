from datetime import datetime
from unittest.mock import patch

from django.core.cache import cache
from django.core.management import call_command
from django.test.testcases import TestCase

from corehq.apps.auditcare.models import (
    AccessAudit,
    AuditcareMigrationMeta,
    NavigationEventAudit,
)
from corehq.apps.auditcare.utils.migration import (
    AuditCareMigrationUtil,
    get_formatted_datetime_string,
)

from .data.audicare_migraion import (
    audit_test_docs,
    failed_docs,
    navigation_test_docs,
)
from .testutils import delete_couch_docs, save_couch_doc


class TestAuditcareMigrationUtil(TestCase):
    util = AuditCareMigrationUtil()
    start_time = datetime(2020, 6, 1)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.key = get_formatted_datetime_string(datetime.now()) + '_' + get_formatted_datetime_string(datetime.now())

    def setUp(self):
        cache.set(self.util.start_key, self.start_time)
        return super().setUp()

    def teardown(self):
        cache.delete(self.util.start_key)
        super().tearDown()

    def test_get_next_batch_start(self):
        start_time = self.util.get_next_batch_start()
        self.assertEqual(start_time, self.start_time)

    @patch(
        'corehq.apps.auditcare.utils.migration.AuditCareMigrationUtil.get_next_batch_start',
        return_value=start_time
    )
    def test_generate_batches(self, _):
        batches = self.util.generate_batches(2, 'h')
        expected_batches = [
            [datetime(2020, 6, 1), datetime(2020, 6, 1, 1)],
            [datetime(2020, 6, 1, 1), datetime(2020, 6, 1, 2)]
        ]
        self.assertEquals(batches, expected_batches)

        batches = self.util.generate_batches(2, 'd')
        expected_batches = [
            [datetime(2020, 6, 1), datetime(2020, 6, 2)],
            [datetime(2020, 6, 2), datetime(2020, 6, 3)]
        ]
        self.assertEquals(batches, expected_batches)

    def test_log_batch_start(self):
        self.util.log_batch_start(self.key)
        self.util.log_batch_start(self.key)

        expected_log = AuditcareMigrationMeta.objects.filter(key=self.key)

        self.assertEqual(len(expected_log), 1)
        self.assertEqual(expected_log[0].key, self.key)
        expected_log[0].delete()

    def test_set_batch_as_finished(self):
        AuditcareMigrationMeta.objects.create(key=self.key, state=AuditcareMigrationMeta.STARTED)

        self.util.set_batch_as_finished(self.key, 30)

        expected_log = AuditcareMigrationMeta.objects.filter(key=self.key)

        self.assertEqual(expected_log[0].state, AuditcareMigrationMeta.FINISHED)
        expected_log[0].delete()

    def test_set_batch_as_errored(self):
        AuditcareMigrationMeta.objects.create(key=self.key, state=AuditcareMigrationMeta.STARTED)

        self.util.set_batch_as_errored(self.key)
        expected_log = AuditcareMigrationMeta.objects.filter(key=self.key)

        self.assertEqual(expected_log[0].state, AuditcareMigrationMeta.ERRORED)
        expected_log[0].delete()

    def test_get_errored_keys(self):
        start_time = datetime(2020, 6, 20)
        end_time = datetime(2020, 6, 21)
        key = get_formatted_datetime_string(start_time) + '_' + get_formatted_datetime_string(end_time)
        obj = AuditcareMigrationMeta.objects.create(key=key, state=AuditcareMigrationMeta.ERRORED)

        keys = self.util.get_errored_keys(1)
        self.assertEqual([[start_time, end_time]], keys)
        obj.delete()

    @classmethod
    def tearDownClass(cls):
        cache.delete(cls.util.start_key)
        AuditcareMigrationMeta.objects.all().delete()
        return super().tearDownClass()


class TestManagementCommand(TestCase):

    @classmethod
    def setUpClass(cls):
        AuditCareMigrationUtil().set_next_batch_start(datetime(2021, 6, 1))
        cls.couch_doc_ids = [save_couch_doc(**doc) for doc in navigation_test_docs + audit_test_docs + failed_docs]

        # setup for adding errored batches
        cls.errored_keys = [
            f'{datetime(2021,5,15)}_{datetime(2021,5,16)}',
            f'{datetime(2021,5,1)}_{datetime(2021,5,2)}',
        ]
        AuditcareMigrationMeta(key=cls.errored_keys[0], state=AuditcareMigrationMeta.ERRORED).save()
        AuditcareMigrationMeta(key=cls.errored_keys[1], state=AuditcareMigrationMeta.ERRORED).save()

        return super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        cache.delete(AuditCareMigrationUtil().start_key)
        NavigationEventAudit.objects.all().delete()
        AccessAudit.objects.all().delete()
        AuditcareMigrationMeta.objects.all().delete()
        delete_couch_docs(cls.couch_doc_ids)
        return super().tearDownClass()

    def test_copy_all_events(self):
        call_command("copy_events_to_sql", "--workers=10", "--batch_by=d")
        total_object_count = NavigationEventAudit.objects.all().count() + AccessAudit.objects.all().count()
        expected_object_count = len(audit_test_docs) + len(navigation_test_docs)
        self.assertEqual(total_object_count, expected_object_count)

    def test_copy_failed_events(self):
        call_command("copy_events_to_sql", "--only_errored=True")

        count_access_objects = AccessAudit.objects.filter(event_date__lte=datetime(2021, 5, 30)).count()
        count_navigation_objects = NavigationEventAudit.objects.filter(
            event_date__lte=datetime(2021, 5, 30)
        ).count()
        self.assertEqual(count_access_objects, 1)
        self.assertEqual(count_navigation_objects, 1)

        meta_state = AuditcareMigrationMeta.objects.filter(
            key__in=self.errored_keys
        ).values_list('state', flat=True)

        self.assertListEqual(list(meta_state), ['f', 'f'])


class TestCopyEventsToSQL(AuditcareTest):
    username = "audit@care.com"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.couch_ids = [save_couch_doc(**doc) for doc in task_docs]

    @classmethod
    def tearDownClass(cls):
        delete_couch_docs(cls.couch_ids)
        AuditcareMigrationMeta.objects.all().delete()
        super().tearDownClass()

    def test_copy(self):
        def _assert():
            self.assertEqual(NavigationEventAudit.objects.count(), 3)
            self.assertEqual(
                [e.path for e in NavigationEventAudit.objects.order_by("-event_date").all()],
                ["just/a/checkpoint", '/a/random/phone/restore/', '/a/test-space/phone/restore/']
            )
            self.assertEqual(
                [e.params for e in NavigationEventAudit.objects.order_by("-event_date").all()],
                ["", "version=2.0&since=...", "version=2.0&since=..."]
            )
            self.assertEqual(AccessAudit.objects.count(), 1)
            self.assertEqual(AccessAudit.objects.first().path, "/a/delmar/login/")

        NavigationEventAudit(event_date=datetime(2021, 2, 1, 4), path="just/a/checkpoint").save()
        copy_events_to_sql(start_time=datetime(2021, 2, 1, 2), end_time=datetime(2021, 2, 1, 5))
        _assert()

        # Re-copying should have no effect
        copy_events_to_sql(start_time=datetime(2021, 2, 1, 2), end_time=datetime(2021, 2, 1, 5))
        _assert()

    @patch('corehq.apps.auditcare.couch_to_sql.COUCH_QUERY_LIMIT', 2)
    def test_copy_with_small_couch_query_limit(self):
        def _assert():
            self.assertEqual(NavigationEventAudit.objects.count(), 4)
            self.assertEqual(
                [e.path for e in NavigationEventAudit.objects.order_by("event_date").all()],
                ['/a/delmar/phone/restore/', '/a/test-space/phone/restore/', '/a/random/phone/restore/', '/a/sandwich/phone/restore/']
            )
            self.assertEqual(
                [e.params for e in NavigationEventAudit.objects.order_by("-event_date").all()],
                ["version=2.0&since=...", "version=2.0&since=...", "version=2.0&since=...", "version=2.0&since=..."]
            )
            self.assertEqual(AccessAudit.objects.count(), 1)
            self.assertEqual(AccessAudit.objects.first().path, "/a/delmar/login/")

        copy_events_to_sql(start_time=datetime(2021, 1, 1), end_time=datetime(2021, 2, 2))
        _assert()
