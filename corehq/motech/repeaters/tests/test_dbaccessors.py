import uuid
from datetime import datetime, timedelta

from django.test import TestCase

from corehq.motech.repeaters.const import State
from corehq.motech.repeaters.models import ConnectionSettings, FormRepeater, SQLRepeatRecord


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
        failed = SQLRepeatRecord(
            domain=cls.domain,
            repeater_id=cls.repeater_id,
            registered_at=before,
            next_check=before,
            payload_id=cls.payload_id_1,
            state=State.Fail,
        )
        failed_hq_error = SQLRepeatRecord(
            domain=cls.domain,
            repeater_id=cls.repeater_id,
            registered_at=before,
            next_check=before,
            payload_id=cls.payload_id_1,
            state=State.Fail,
        )
        success = SQLRepeatRecord(
            domain=cls.domain,
            repeater_id=cls.repeater_id,
            registered_at=before,
            payload_id=cls.payload_id_2,
            state=State.Success,
        )
        pending = SQLRepeatRecord(
            domain=cls.domain,
            repeater_id=cls.repeater_id,
            registered_at=before,
            next_check=before,
            payload_id=cls.payload_id_2,
        )
        overdue = SQLRepeatRecord(
            domain=cls.domain,
            repeater_id=cls.repeater_id,
            registered_at=before,
            next_check=before - timedelta(minutes=10),
            payload_id=cls.payload_id_2,
        )
        cancelled = SQLRepeatRecord(
            domain=cls.domain,
            repeater_id=cls.repeater_id,
            registered_at=before,
            payload_id=cls.payload_id_2,
            state=State.Cancelled,
        )
        empty = SQLRepeatRecord(
            domain=cls.domain,
            repeater_id=cls.repeater_id,
            registered_at=before,
            payload_id=cls.payload_id_2,
            state=State.Empty,
        )
        other_id = SQLRepeatRecord(
            domain=cls.domain,
            repeater_id=cls.other_id,
            registered_at=before,
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
        SQLRepeatRecord.objects.bulk_create(cls.records)

    def test_get_paged_repeat_records(self):
        records = SQLRepeatRecord.objects.page(self.domain, 0, 2)
        self.assertEqual(len(records), 2)

    def test_get_paged_repeat_records_with_repeater_id(self):
        records = SQLRepeatRecord.objects.page(self.domain, 0, 2, repeater_id=self.other_id)
        self.assertEqual(len(records), 1)

    def test_get_paged_repeat_records_with_state(self):
        records = SQLRepeatRecord.objects.page(self.domain, 0, 10, state=State.Pending)
        self.assertEqual(len(records), 3)

    def test_get_paged_repeat_records_wrong_domain(self):
        records = SQLRepeatRecord.objects.page('wrong-domain', 0, 2)
        self.assertEqual(len(records), 0)

    def test_get_all_paged_repeat_records(self):
        records = SQLRepeatRecord.objects.page(self.domain, 0, 10)
        self.assertEqual(len(records), len(self.records))  # get all the records that were created

    def test_get_all_repeat_records_by_domain_wrong_domain(self):
        records = list(SQLRepeatRecord.objects.iterate("wrong-domain"))
        self.assertEqual(len(records), 0)

    def test_get_all_repeat_records_by_domain_with_repeater_id(self):
        records = list(SQLRepeatRecord.objects.iterate(self.domain, repeater_id=self.repeater_id))
        self.assertEqual(len(records), 7)

    def test_get_all_repeat_records_by_domain(self):
        records = list(SQLRepeatRecord.objects.iterate(self.domain))
        self.assertEqual(len(records), len(self.records))

    def test_get_repeat_records_by_payload_id(self):
        id_1_records = list(SQLRepeatRecord.objects.filter(domain=self.domain, payload_id=self.payload_id_1))
        self.assertEqual(len(id_1_records), 2)
        self.assertItemsEqual([r.id for r in id_1_records], [r.id for r in self.records[:2]])

        id_2_records = list(SQLRepeatRecord.objects.filter(domain=self.domain, payload_id=self.payload_id_2))
        self.assertEqual(len(id_2_records), 6)
        self.assertItemsEqual([r.id for r in id_2_records], [r.id for r in self.records[2:]])
