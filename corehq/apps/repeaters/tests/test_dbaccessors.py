from datetime import datetime, timedelta
from django.test import TestCase

from corehq.apps.repeaters.dbaccessors import (
    get_pending_repeat_record_count,
    get_success_repeat_record_count,
    get_failure_repeat_record_count,
    get_repeat_record_count,
    get_repeaters_by_domain,
    get_paged_repeat_records,
    iterate_repeat_records,
)
from corehq.apps.repeaters.models import RepeatRecord, CaseRepeater
from corehq.apps.repeaters.const import RECORD_PENDING_STATE


class TestRepeatRecordDBAccessors(TestCase):
    repeater_id = '1234'
    other_id = '5678'
    domain = 'test-domain-2'

    @classmethod
    def setUpClass(cls):
        before = datetime.utcnow() - timedelta(minutes=5)

        failed = RepeatRecord(
            domain=cls.domain,
            failure_reason='Some python error',
            repeater_id=cls.repeater_id,
            next_event=before,
        )
        success = RepeatRecord(
            domain=cls.domain,
            succeeded=True,
            repeater_id=cls.repeater_id,
            next_event=before,
        )
        pending = RepeatRecord(
            domain=cls.domain,
            succeeded=False,
            repeater_id=cls.repeater_id,
            next_event=before,
        )
        other_id = RepeatRecord(
            domain=cls.domain,
            succeeded=False,
            repeater_id=cls.other_id,
            next_event=before,
        )

        cls.records = [
            failed,
            success,
            pending,
            other_id,
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

    def test_get_paged_repeat_records_with_state_and_no_records(self):
        count = get_repeat_record_count('wrong-domain', state=RECORD_PENDING_STATE)
        self.assertEqual(count, 0)

    def test_get_paged_repeat_records(self):
        records = get_paged_repeat_records(self.domain, 0, 2)
        self.assertEqual(len(records), 2)

    def test_get_paged_repeat_records_with_repeater_id(self):
        records = get_paged_repeat_records(self.domain, 0, 2, repeater_id=self.other_id)
        self.assertEqual(len(records), 1)

    def test_get_paged_repeat_records_with_state(self):
        records = get_paged_repeat_records(self.domain, 0, 10, state=RECORD_PENDING_STATE)
        self.assertEqual(len(records), 2)

    def test_get_paged_repeat_records_wrong_domain(self):
        records = get_paged_repeat_records('wrong-domain', 0, 2)
        self.assertEqual(len(records), 0)

    def test_iterate_repeat_records(self):
        records = list(iterate_repeat_records(datetime.utcnow(), chunk_size=2))
        self.assertEqual(len(records), 3)  # Should grab all but the succeeded one


class TestRepeatersDBAccessors(TestCase):
    domain = 'test-domain'

    @classmethod
    def setUpClass(cls):
        repeater = CaseRepeater(
            domain=cls.domain,
        )
        cls.repeaters = [
            repeater
        ]

        for repeater in cls.repeaters:
            repeater.save()

    @classmethod
    def tearDownClass(cls):
        for repeater in cls.repeaters:
            repeater.delete()

    def test_get_repeaters_by_domain(self):
        repeaters = get_repeaters_by_domain(self.domain)
        self.assertEqual(len(repeaters), 1)
        self.assertEqual(repeaters[0].__class__, CaseRepeater)
