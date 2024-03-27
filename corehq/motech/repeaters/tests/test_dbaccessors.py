import uuid
from datetime import datetime, timedelta

from django.test import TestCase

from corehq.motech.repeaters.const import RECORD_PENDING_STATE
from corehq.motech.repeaters.dbaccessors import (
    get_cancelled_repeat_record_count,
    get_domains_that_have_repeat_records,
    get_failure_repeat_record_count,
    get_overdue_repeat_record_count,
    get_paged_repeat_records,
    get_pending_repeat_record_count,
    get_repeat_record_count,
    get_repeat_records_by_payload_id,
    get_success_repeat_record_count,
    iter_repeat_records_by_domain,
    iterate_repeat_record_ids,
)
from corehq.motech.repeaters.models import ConnectionSettings, FormRepeater, RepeatRecord


class TestRepeatRecordDBAccessors(TestCase):
    repeater_id = '1234a764a9a0b37ef8254e121ea4b46d'
    other_id = '56789e3a6eb641f8b0313e5a14d4b02f'
    domain = 'test-domain-2'

    @classmethod
    def setUpClass(cls):
        super(TestRepeatRecordDBAccessors, cls).setUpClass()
        before = datetime.utcnow() - timedelta(minutes=5)
        cnx = ConnectionSettings.objects.create(
            domain=cls.domain,
            name='Test API',
            url="http://localhost/api/"
        )
        FormRepeater.objects.create(
            id=uuid.UUID(cls.repeater_id),
            domain=cls.domain,
            format='form_xml',
            connection_settings=cnx,
        )
        FormRepeater.objects.create(
            id=uuid.UUID(cls.other_id),
            domain=cls.domain,
            format='form_xml',
            connection_settings=cnx,
        )
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
        cancelled = RepeatRecord(
            domain=cls.domain,
            succeeded=False,
            cancelled=True,
            repeater_id=cls.repeater_id,
            payload_id=cls.payload_id_2,
        )
        empty = RepeatRecord(
            domain=cls.domain,
            succeeded=True,
            cancelled=True,
            repeater_id=cls.repeater_id,
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
            cancelled,
            empty,
            other_id,
        ]
        cls.addClassCleanup(RepeatRecord.bulk_delete, cls.records)

        for record in cls.records:
            record.registered_on = before
            record.save()

    def test_get_pending_repeat_record_count(self):
        count = get_pending_repeat_record_count(self.domain, self.repeater_id)
        self.assertEqual(count, 2)

    def test_get_success_repeat_record_count(self):
        count = get_success_repeat_record_count(self.domain, self.repeater_id)
        self.assertEqual(count, 2)  # Empty records are included

    def test_get_failure_repeat_record_count(self):
        count = get_failure_repeat_record_count(self.domain, self.repeater_id)
        self.assertEqual(count, 2)

    def test_get_cancelled_repeat_record_count(self):
        count = get_cancelled_repeat_record_count(self.domain, self.repeater_id)
        self.assertEqual(count, 1)  # Empty records are not included

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
        self.assertEqual(len(records), 7)

    def test_get_all_repeat_records_by_domain(self):
        records = list(iter_repeat_records_by_domain(self.domain))
        self.assertEqual(len(records), len(self.records))

    def test_get_repeat_records_by_payload_id(self):
        id_1_records = list(get_repeat_records_by_payload_id(self.domain, self.payload_id_1))
        self.assertEqual(len(id_1_records), 2)
        self.assertItemsEqual([r._id for r in id_1_records], [r._id for r in self.records[:2]])

        id_2_records = list(get_repeat_records_by_payload_id(self.domain, self.payload_id_2))
        self.assertEqual(len(id_2_records), 6)
        self.assertItemsEqual([r._id for r in id_2_records], [r._id for r in self.records[2:]])


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
        cls.addClassCleanup(RepeatRecord.bulk_delete, cls.records)

    def test_get_domains_that_have_repeat_records(self):
        self.assertEqual(get_domains_that_have_repeat_records(), ['a', 'b', 'c'])
