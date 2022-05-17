import uuid
from datetime import datetime, timedelta

from django.test import TestCase

from corehq.motech.models import ConnectionSettings
from corehq.motech.repeaters.const import (
    RECORD_PENDING_STATE,
)
from corehq.motech.repeaters.dbaccessors import (
    get_all_repeater_docs,
    get_domains_that_have_repeat_records,
    get_failure_repeat_record_count,
    get_overdue_repeat_record_count,
    get_paged_repeat_records,
    get_pending_repeat_record_count,
    get_repeat_record_count,
    get_repeat_records_by_payload_id,
    get_repeater_count_for_domains,
    get_repeaters_by_domain,
    get_success_repeat_record_count,
    iter_repeat_records_by_domain,
    iterate_repeat_record_ids,
)
from corehq.motech.repeaters.models import CaseRepeater, RepeatRecord


class TestRepeatRecordDBAccessors(TestCase):
    repeater_id = '1234'
    other_id = '5678'
    domain = 'test-domain-2'

    @classmethod
    def setUpClass(cls):
        super(TestRepeatRecordDBAccessors, cls).setUpClass()
        before = datetime.utcnow() - timedelta(minutes=5)
        cls.payload_id_1 = uuid.uuid4().hex
        cls.payload_id_2 = uuid.uuid4().hex
        failed = RepeatRecord(
            domain=cls.domain,
            failure_reason='Some python error',
            repeater_id=cls.repeater_id,
            next_check=before,
            payload_id=cls.payload_id_1,
        )
        failed_hq_error = RepeatRecord(
            domain=cls.domain,
            failure_reason='Some python error',
            repeater_id=cls.repeater_id,
            next_check=before,
            payload_id=cls.payload_id_1,
        )
        failed_hq_error.doc_type += '-Failed'
        success = RepeatRecord(
            domain=cls.domain,
            succeeded=True,
            repeater_id=cls.repeater_id,
            next_check=before,
            payload_id=cls.payload_id_2,
        )
        pending = RepeatRecord(
            domain=cls.domain,
            succeeded=False,
            repeater_id=cls.repeater_id,
            next_check=before,
            payload_id=cls.payload_id_2,
        )
        overdue = RepeatRecord(
            domain=cls.domain,
            succeeded=False,
            repeater_id=cls.repeater_id,
            next_check=before - timedelta(minutes=10),
            payload_id=cls.payload_id_2,
        )
        other_id = RepeatRecord(
            domain=cls.domain,
            succeeded=False,
            repeater_id=cls.other_id,
            next_check=before,
            payload_id=cls.payload_id_2,
        )

        cls.records = [
            failed,
            failed_hq_error,
            success,
            pending,
            overdue,
            other_id,
        ]

        for record in cls.records:
            record.save()

    @classmethod
    def tearDownClass(cls):
        for record in cls.records:
            record.delete()
        super(TestRepeatRecordDBAccessors, cls).tearDownClass()

    def test_get_pending_repeat_record_count(self):
        count = get_pending_repeat_record_count(self.domain, self.repeater_id)
        self.assertEqual(count, 2)

    def test_get_success_repeat_record_count(self):
        count = get_success_repeat_record_count(self.domain, self.repeater_id)
        self.assertEqual(count, 1)

    def test_get_failure_repeat_record_count(self):
        count = get_failure_repeat_record_count(self.domain, self.repeater_id)
        self.assertEqual(count, 2)

    def test_get_repeat_record_count_with_state_and_no_repeater(self):
        count = get_repeat_record_count(self.domain, state=RECORD_PENDING_STATE)
        self.assertEqual(count, 3)

    def test_get_repeat_record_count_with_repeater_id_and_no_state(self):
        count = get_repeat_record_count(self.domain, repeater_id=self.other_id)
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
        self.assertEqual(len(records), 3)

    def test_get_paged_repeat_records_wrong_domain(self):
        records = get_paged_repeat_records('wrong-domain', 0, 2)
        self.assertEqual(len(records), 0)

    def test_get_all_paged_repeat_records(self):
        records = get_paged_repeat_records(self.domain, 0, 10)
        self.assertEqual(len(records), len(self.records))  # get all the records that were created

    def test_iterate_repeat_records(self):
        records = list(iterate_repeat_record_ids(datetime.utcnow(), chunk_size=2))
        self.assertEqual(len(records), 4)  # Should grab all but the succeeded one

    def test_get_overdue_repeat_record_count(self):
        overdue_count = get_overdue_repeat_record_count()
        self.assertEqual(overdue_count, 1)

    def test_get_all_repeat_records_by_domain_wrong_domain(self):
        records = list(iter_repeat_records_by_domain("wrong-domain"))
        self.assertEqual(len(records), 0)

    def test_get_all_repeat_records_by_domain_with_repeater_id(self):
        records = list(iter_repeat_records_by_domain(self.domain, repeater_id=self.repeater_id))
        self.assertEqual(len(records), 5)

    def test_get_all_repeat_records_by_domain(self):
        records = list(iter_repeat_records_by_domain(self.domain))
        self.assertEqual(len(records), len(self.records))

    def test_get_repeat_records_by_payload_id(self):
        id_1_records = list(get_repeat_records_by_payload_id(self.domain, self.payload_id_1))
        self.assertEqual(len(id_1_records), 2)
        self.assertItemsEqual([r._id for r in id_1_records], [r._id for r in self.records[0:2]])

        id_2_records = list(get_repeat_records_by_payload_id(self.domain, self.payload_id_2))
        self.assertEqual(len(id_2_records), 4)
        self.assertItemsEqual([r._id for r in id_2_records], [r._id for r in self.records[2:6]])


class TestRepeatersDBAccessors(TestCase):

    domain_1 = 'test-domain-3'
    domain_2 = 'domain-test-3'

    @classmethod
    def setUpClass(cls):
        super(TestRepeatersDBAccessors, cls).setUpClass()
        cls.conn = ConnectionSettings(domain=cls.domain_1, url='http://url.com')
        cls.conn.save()
        repeater_1 = CaseRepeater(
            domain=cls.domain_1,
            format='case_json',
            connection_settings_id=cls.conn.id,
        )
        repeater_2 = CaseRepeater(
            domain=cls.domain_2,
            connection_settings_id=cls.conn.id,
            format='case_json',
        )
        cls.repeaters = [
            repeater_1,
            repeater_2
        ]

        for repeater in cls.repeaters:
            repeater.save()

    @classmethod
    def tearDownClass(cls):
        for repeater in cls.repeaters:
            repeater.delete()
        super(TestRepeatersDBAccessors, cls).tearDownClass()

    def test_get_repeaters_by_domain(self):
        repeaters = get_repeaters_by_domain(self.domain_1)
        self.assertEqual(len(repeaters), 1)
        self.assertEqual(repeaters[0].__class__, CaseRepeater)

    def test_get_all_repeater_docs(self):
        repeaters = get_all_repeater_docs()
        self.assertEqual(len(repeaters), 2)

    def test_get_repeater_count_for_domains(self):
        self.assertEqual(
            get_repeater_count_for_domains([self.domain_1]),
            1
        )
        self.assertEqual(
            get_repeater_count_for_domains([self.domain_1, self.domain_2]),
            2
        )


class TestOtherDBAccessors(TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestOtherDBAccessors, cls).setUpClass()
        cls.records = [
            RepeatRecord(domain='a'),
            RepeatRecord(domain='b'),
            RepeatRecord(domain='c'),
        ]
        RepeatRecord.bulk_save(cls.records)

    @classmethod
    def tearDownClass(cls):
        RepeatRecord.bulk_delete(cls.records)
        super(TestOtherDBAccessors, cls).tearDownClass()

    def test_get_domains_that_have_repeat_records(self):
        self.assertEqual(get_domains_that_have_repeat_records(), ['a', 'b', 'c'])
