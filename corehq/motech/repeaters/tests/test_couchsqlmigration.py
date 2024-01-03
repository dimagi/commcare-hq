from datetime import datetime, timedelta
from uuid import UUID, uuid4

from django.test import TestCase

from dimagi.utils.parsing import json_format_datetime

from .. import models
from ..dbaccessors import delete_all_repeat_records
from ..management.commands.populate_repeatrecords import Command, get_state
from ..models import ConnectionSettings, RepeatRecord, SQLRepeatRecord

REPEATER_ID_1 = "5c739aaa0cb44a24a71933616258f3b6"
REPEATER_ID_2 = "64b6bf1758ed4f2a8944d6f34c2811c2"


class BaseRepeatRecordCouchToSQLTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        url = 'https://www.example.com/api/'
        conn = ConnectionSettings.objects.create(domain="test", name=url, url=url)
        cls.repeater1 = models.FormRepeater.objects.create(
            id=UUID(REPEATER_ID_1),
            domain="test",
            connection_settings=conn,
            include_app_id_param=False,
        )
        cls.repeater2 = models.FormRepeater.objects.create(
            id=UUID(REPEATER_ID_2),
            domain="test",
            connection_settings=conn,
            include_app_id_param=False,
        )

    def create_repeat_record(self, unwrap_doc=True):
        def data(**extra):
            return {
                'domain': repeater.domain,
                'payload_id': payload_id,
                **extra,
            }
        repeater = self.repeater1
        now = datetime.utcnow().replace(microsecond=0)
        payload_id = uuid4().hex
        obj = SQLRepeatRecord(repeater_id=repeater.id, registered_at=now, **data())
        doc = RepeatRecord.wrap(data(
            doc_type="RepeatRecord",
            repeater_type='Echo',
            repeater_id=repeater.repeater_id,
            registered_on=json_format_datetime(now),
        ))
        if unwrap_doc:
            doc = doc.to_json()
        return doc, obj


class TestRepeatRecordCouchToSQLDiff(BaseRepeatRecordCouchToSQLTest):

    def test_no_diff(self):
        doc, obj = self.create_repeat_record()
        self.assertEqual(self.diff(doc, obj), [])

    def test_diff_domain(self):
        doc, obj = self.create_repeat_record()
        doc['domain'] = 'other-domain'
        self.assertEqual(
            self.diff(doc, obj),
            ["domain: couch value 'other-domain' != sql value 'test'"],
        )

    def test_diff_payload_id(self):
        doc, obj = self.create_repeat_record()
        obj.payload_id = uuid4().hex
        self.assertEqual(
            self.diff(doc, obj),
            [f"payload_id: couch value '{doc['payload_id']}' != sql value '{obj.payload_id}'"],
        )

    def test_diff_repeater_id(self):
        doc, obj = self.create_repeat_record()
        obj.repeater_id = self.repeater2.id
        self.assertEqual(
            self.diff(doc, obj),
            [f"repeater_id: couch value '{REPEATER_ID_1}' != sql value '{REPEATER_ID_2}'"],
        )

    def test_diff_state(self):
        doc, obj = self.create_repeat_record()
        obj.state = models.State.Cancelled
        self.assertEqual(
            self.diff(doc, obj),
            ["state: couch value <State.Pending: 1> != sql value <State.Cancelled: 8>"],
        )

    def test_diff_registered_at(self):
        doc, obj = self.create_repeat_record()
        hour_hence = datetime.utcnow() + timedelta(hours=1)
        obj.registered_at = hour_hence
        self.assertEqual(
            self.diff(doc, obj),
            [f"registered_at: couch value {doc['registered_on']!r} "
             f"!= sql value {json_format_datetime(hour_hence)!r}"],
        )

    def test_diff_next_check(self):
        doc, obj = self.create_repeat_record()
        hour_hence = datetime.utcnow() + timedelta(hours=1)
        obj.next_check = hour_hence
        self.assertEqual(
            self.diff(doc, obj),
            [f"next_check: couch value {doc['next_check']!r} "
             f"!= sql value {json_format_datetime(hour_hence)!r}"],
        )

    def diff(self, doc, obj):
        return do_diff(Command, doc, obj)


class TestRepeatRecordCouchToSQLMigration(BaseRepeatRecordCouchToSQLTest):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.db = RepeatRecord.get_db()

    def tearDown(self):
        delete_all_repeat_records()
        super().tearDown()

    def test_sync_to_couch(self):
        doc, obj = self.create_repeat_record()
        obj.save()
        couch_obj = self.db.get(obj._migration_couch_id)
        self.assertEqual(self.diff(couch_obj, obj), [])

        hour_hence = datetime.utcnow() + timedelta(hours=1)
        obj.payload_id = payload_id = uuid4().hex
        obj.repeater_id = self.repeater2.id
        obj.state = models.State.Fail
        obj.registered_at = hour_hence
        obj.next_check = hour_hence
        obj.save()
        doc = self.db.get(obj._migration_couch_id)
        self.assertEqual(doc['payload_id'], payload_id)
        self.assertEqual(doc['repeater_id'], self.repeater2.repeater_id)
        self.assertEqual(get_state(doc), models.State.Fail)
        self.assertEqual(doc['registered_on'], json_format_datetime(hour_hence))
        self.assertEqual(doc['next_check'], json_format_datetime(hour_hence))

    def test_sync_to_sql(self):
        doc, obj = self.create_repeat_record(unwrap_doc=False)
        doc.save()
        self.assertEqual(
            self.diff(doc.to_json(), SQLRepeatRecord.objects.get(couch_id=doc._id)),
            [],
        )

        hour_hence = datetime.utcnow() + timedelta(hours=1)
        doc.payload_id = payload_id = uuid4().hex
        doc.repeater_id = REPEATER_ID_2
        doc.failure_reason = "something happened"
        doc.registered_on = hour_hence
        doc.next_check = hour_hence
        doc.save()
        obj = SQLRepeatRecord.objects.get(couch_id=doc._id)
        self.assertEqual(obj.payload_id, payload_id)
        self.assertEqual(obj.repeater.repeater_id, REPEATER_ID_2)
        self.assertEqual(obj.state, models.State.Fail)
        self.assertEqual(obj.registered_at, hour_hence)
        self.assertEqual(obj.next_check, hour_hence)

    def diff(self, doc, obj):
        return do_diff(Command, doc, obj)


def do_diff(Command, doc, obj):
    result = Command.diff_couch_and_sql(doc, obj)
    return [x for x in result if x is not None]
