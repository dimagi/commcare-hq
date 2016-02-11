from django.test import TestCase

from corehq.apps.repeaters.dbaccessors import (
    get_pending_repeat_record_count,
    get_success_repeat_record_count,
    get_failure_repeat_record_count,
)
from corehq.apps.repeaters.models import RepeatRecord


class TestDBAccessors(TestCase):
    dependent_apps = ['corehq.apps.repeaters', 'corehq.couchapps']
    repeater_id = '1234'
    domain = 'test-domain'

    @classmethod
    def setUpClass(cls):
        failed = RepeatRecord(
            domain=cls.domain,
            failure_reason='Some python error',
            repeater_id=cls.repeater_id,
        )
        success = RepeatRecord(
            domain=cls.domain,
            succeeded=True,
            repeater_id=cls.repeater_id,
        )
        pending = RepeatRecord(
            domain=cls.domain,
            succeeded=False,
            repeater_id=cls.repeater_id,
        )

        cls.records = [
            failed,
            success,
            pending,
        ]

        for record in cls.records:
            record.save()

    @classmethod
    def tearDownClass(cls):
        for record in cls.records:
            record.delete()

    def test_get_pending_repeat_record_count(self):
        count = get_pending_repeat_record_count(self.domain, self.repeater_id)
        self.assertEqual(count, 1)

    def test_get_success_repeat_record_count(self):
        count = get_success_repeat_record_count(self.domain, self.repeater_id)
        self.assertEqual(count, 1)

    def test_get_failure_repeat_record_count(self):
        count = get_failure_repeat_record_count(self.domain, self.repeater_id)
        self.assertEqual(count, 1)
