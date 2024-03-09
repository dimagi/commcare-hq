from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from uuid import UUID, uuid4

from django.db import connection, transaction
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from django.utils.functional import cached_property

from testil import tempdir

from dimagi.utils.parsing import json_format_datetime

from .. import models
from ..dbaccessors import delete_all_repeat_records
from ..management.commands.populate_repeatrecords import Command, get_state
from ..models import (
    ConnectionSettings,
    RepeatRecord,
    RepeatRecordAttempt,
    SQLRepeatRecord,
    SQLRepeatRecordAttempt,
)

REPEATER_ID_1 = "5c739aaa0cb44a24a71933616258f3b6"
REPEATER_ID_2 = "64b6bf1758ed4f2a8944d6f34c2811c2"
REPEATER_ID_3 = "123b7a7008b447a4a0de61f6077a0353"


class TestRepeatRecordModel(SimpleTestCase):

    def test_set_state_does_not_overwrite_failure_reason(self):
        rec = RepeatRecord(failure_reason="Mildew that should not go away")
        rec.state = models.State.Fail
        self.assertEqual(rec.failure_reason, "Mildew that should not go away")


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

    def create_repeat_record(self, unwrap_doc=True, repeater=None):
        def data(**extra):
            return {
                'domain': repeater.domain,
                'payload_id': payload_id,
                **extra,
            }
        if repeater is None:
            repeater = self.repeater1
        now = datetime.utcnow().replace(microsecond=0)
        payload_id = uuid4().hex
        first_attempt = datetime.utcnow() - timedelta(minutes=10)
        second_attempt = datetime.utcnow() - timedelta(minutes=8)
        obj = SQLRepeatRecord(repeater_id=repeater.id, registered_at=now, **data())
        obj._prefetched_objects_cache = {"attempt_set": [
            SQLRepeatRecordAttempt(
                state=models.State.Fail,
                message="something bad happened",
                traceback="the parrot has left the building",
                created_at=first_attempt,
            ),
            SQLRepeatRecordAttempt(
                state=models.State.Success,
                message="polly wants a cracker",
                created_at=second_attempt,
            ),
        ]}
        doc = RepeatRecord.wrap(data(
            doc_type="RepeatRecord",
            repeater_type='Echo',
            repeater_id=repeater.repeater_id,
            registered_on=json_format_datetime(now),
            attempts=[
                {
                    "datetime": first_attempt.isoformat() + "Z",
                    "failure_reason": "something bad happened",
                    "next_check": second_attempt.isoformat() + "Z",
                },
                {
                    "datetime": second_attempt.isoformat() + "Z",
                    "success_response": "polly wants a cracker",
                    "succeeded": True,
                },
            ],
            overall_tries=2,
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
        obj.state = models.State.Empty
        self.assertEqual(
            self.diff(doc, obj),
            ["state: couch value <State.Pending: 1> != sql value <State.Empty: 16>"],
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

    def test_diff_next_check_when_couch_value_is_obsolete(self):
        doc, obj = self.create_repeat_record(unwrap_doc=False)
        doc.state = models.State.Success
        doc.next_check = datetime.utcnow() + timedelta(days=2)
        obj.state = models.State.Success
        obj.next_check = None
        self.assertEqual(self.diff(doc.to_json(), obj), [])

    def test_diff_failure_reason(self):
        doc, obj = self.create_repeat_record()
        doc["failure_reason"] = "polly didn't get a cracker"
        obj.state = models.State.Fail
        self.assertEqual(
            self.diff(doc, obj),
            [
                'failure_reason: couch value "polly didn\'t get a cracker" '
                '!= sql value \'polly wants a cracker\'',
            ],
        )

    def test_diff_empty_couch_failure_reason(self):
        doc, obj = self.create_repeat_record()
        doc["failure_reason"] = ""
        doc["cancelled"] = True
        doc["attempts"].pop()
        obj.state = models.State.Cancelled
        obj.attempts.pop()
        self.assertEqual(self.diff(doc, obj), [])

    def test_diff_attempts(self):
        doc, obj = self.create_repeat_record()
        doc["attempts"][0]["succeeded"] = True
        doc["attempts"][0]["failure_reason"] = None
        doc["attempts"][1]["datetime"] = "2020-01-01T00:00:00.000000Z"
        doc["attempts"][1]["success_response"] = None
        obj.attempts[1].message = ''
        couch_datetime = repr(datetime(2020, 1, 1, 0, 0))
        sql_created_at = repr(obj.attempts[1].created_at)
        self.assertEqual(
            self.diff(doc, obj),
            [
                "attempts[0].state: couch value <State.Success: 4> != sql value <State.Fail: 2>",
                "attempts[0].message: couch value '' != sql value 'something bad happened'",
                f"attempts[1].created_at: couch value {couch_datetime} != sql value {sql_created_at}",
            ],
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
        Command.discard_resume_state()
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
        del obj.attempts[1]
        obj.save()
        doc = self.db.get(obj._migration_couch_id)
        self.assertEqual(doc['payload_id'], payload_id)
        self.assertEqual(doc['repeater_id'], self.repeater2.repeater_id)
        self.assertEqual(doc['failure_reason'], "something bad happened")
        self.assertEqual(get_state(doc), models.State.Fail)
        self.assertEqual(doc['registered_on'], json_format_datetime(hour_hence))
        self.assertEqual(doc['next_check'], json_format_datetime(hour_hence))
        self.assertEqual(doc['attempts'][0]["succeeded"], False)
        self.assertEqual(doc['attempts'][0]["failure_reason"], "something bad happened")
        self.assertEqual(doc['overall_tries'], 1)

    def test_sync_to_sql(self):
        doc, obj = self.create_repeat_record(unwrap_doc=False)
        doc.save(sync_attempts=True)
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
        del doc.attempts[0]
        doc.save()
        obj = SQLRepeatRecord.objects.get(couch_id=doc._id)
        self.assertEqual(obj.payload_id, payload_id)
        self.assertEqual(obj.repeater.repeater_id, REPEATER_ID_2)
        self.assertEqual(obj.state, models.State.Fail)
        self.assertEqual(obj.registered_at, hour_hence)
        self.assertEqual(obj.next_check, hour_hence)
        # attempts are not synced to SQL by default
        self.assertEqual(obj.attempts[0].state, models.State.Fail)
        self.assertEqual(len(obj.attempts), 2)

    def test_sync_attempts_to_sql(self):
        doc, obj = self.create_repeat_record(unwrap_doc=False)
        doc.save(sync_attempts=True)

        del doc.attempts[0]
        doc.save(sync_attempts=True)
        obj = SQLRepeatRecord.objects.get(couch_id=doc._id)
        self.assertEqual(obj.attempts[0].state, models.State.Success)
        self.assertEqual(len(obj.attempts), 1)

    def test_sync_attempt_with_null_message_to_sql(self):
        doc, obj = self.create_repeat_record(unwrap_doc=False)
        doc.save(sync_attempts=True)

        doc.attempts[1].success_response = None
        doc.save(sync_attempts=True)
        obj = SQLRepeatRecord.objects.get(couch_id=doc._id)
        self.assertEqual(obj.attempts[1].message, '')

    def test_repeater_syncs_attempt_to_couch_on_sql_record_add_attempt(self):
        doc, obj = self.create_repeat_record(unwrap_doc=False)
        doc.attempts.pop()
        assert len(doc.attempts) == 1, doc.attempts
        obj._prefetched_objects_cache["attempt_set"].pop()
        doc.save(sync_attempts=True)
        obj = SQLRepeatRecord.objects.get(couch_id=doc._id)
        self.assertEqual(self.diff(doc.to_json(), obj), [])

        obj.add_success_attempt(True)
        doc = self.db.get(obj._migration_couch_id)
        self.assertEqual(len(doc["attempts"]), 2, doc["attempts"])
        self.assertEqual(doc["attempts"][-1]["succeeded"], True)
        self.assertFalse(doc["attempts"][-1]["success_response"])

    def test_repeater_add_attempt_syncs_to_sql(self):
        doc, obj = self.create_repeat_record(unwrap_doc=False)
        doc.save(sync_attempts=True)
        obj = SQLRepeatRecord.objects.get(couch_id=doc._id)
        initial_attempt_ids = [a.id for a in obj.attempts]

        attempt = RepeatRecordAttempt(
            datetime=datetime.utcnow(),
            success_response="manual resend",
            succeeded=True,
        )
        doc.add_attempt(attempt)
        doc.save()
        attempts = list(obj.attempts)
        self.assertEqual(
            initial_attempt_ids,
            [attempts[0].id, attempts[1].id],
            "initial attempts should not be deleted/recreated"
        )
        self.assertEqual(len(attempts), 3, [a.message for a in attempts])
        self.assertEqual(attempts[-1].message, "manual resend")

    def test_repeater_syncs_attempt_to_sql_when_sql_record_does_not_exist(self):
        doc, obj = self.create_repeat_record(unwrap_doc=False)
        doc.save(sync_to_sql=False)

        attempt = RepeatRecordAttempt(
            datetime=datetime.utcnow(),
            success_response="manual resend",
            succeeded=True,
        )
        doc.add_attempt(attempt)
        doc.save()
        obj = SQLRepeatRecord.objects.get(couch_id=doc._id)
        attempts = list(obj.attempts)
        self.assertEqual(len(attempts), 3, [a.message for a in attempts])
        self.assertEqual(attempts[-1].message, "manual resend")

    def test_migration(self):
        @property
        def dont_lookup_repeater(self):
            # fail if inefficient repeater lookup is attempted
            raise Exception("this should not happen")

        doc, obj = self.create_repeat_record(unwrap_doc=False)
        doc.save(sync_to_sql=False)
        with patch.object(type(doc), "repeater", dont_lookup_repeater):
            call_command('populate_repeatrecords')
        self.assertEqual(
            self.diff(doc.to_json(), SQLRepeatRecord.objects.get(couch_id=doc._id)),
            [],
        )

    def test_migration_fixup_diffs(self):
        # Additional call should apply any updates
        doc, obj = self.create_repeat_record(unwrap_doc=False)
        doc.save(sync_attempts=True)
        doc.payload_id = payload_id = uuid4().hex
        doc.repeater_id = REPEATER_ID_2
        doc.failure_reason = "something bad happened"
        doc.registered_on = datetime.utcnow() + timedelta(hours=1)
        del doc.attempts[1]
        doc.save(sync_to_sql=False)

        with templog() as log:
            call_command('populate_repeatrecords', log_path=log.path)
            self.assertIn(f'Doc "{doc._id}" has differences:\n', log.content)
            self.assertIn(f"payload_id: couch value {payload_id!r} != sql value {obj.payload_id!r}\n", log.content)
            self.assertIn(
                f"repeater_id: couch value '{REPEATER_ID_2}' != sql value '{REPEATER_ID_1}'\n", log.content)
            self.assertIn("state: couch value <State.Fail: 2> != sql value 1\n", log.content)
            self.assertIn("registered_at: couch value '", log.content)

            call_command('populate_repeatrecords', fixup_diffs=log.path)
            self.assertEqual(
                self.diff(doc.to_json(), SQLRepeatRecord.objects.get(couch_id=doc._id)),
                [],
            )

    def test_migration_with_deleted_repeater(self):
        doc, obj = self.create_repeat_record(unwrap_doc=False)
        repeater1_id = self.repeater1.id
        self.addCleanup(setattr, self.repeater1, "id", repeater1_id)
        self.repeater1.delete()
        doc_id = self.db.save_doc(doc.to_json())["id"]
        assert RepeatRecord.get(doc_id) is not None, "missing record"
        with templog() as log, patch.object(transaction, "atomic", atomic_check):
            call_command('populate_repeatrecords', log_path=log.path)
            self.assertIn(f"Ignored model for RepeatRecord with id {doc_id}\n", log.content)

    def test_migration_with_null_attempt_message(self):
        doc, _ = self.create_repeat_record(unwrap_doc=False)
        doc.attempts[1].message = None
        doc.save(sync_to_sql=False)
        with templog() as log, patch.object(transaction, "atomic", atomic_check):
            call_command('populate_repeatrecords', log_path=log.path)
            self.assertNotIn('has differences:', log.content)
        obj = SQLRepeatRecord.objects.get(couch_id=doc._id)
        self.assertEqual(obj.attempts[1].message, '')

    def test_migration_with_null_registered_at(self):
        doc, _ = self.create_repeat_record(unwrap_doc=False)
        doc.registered_on = None
        doc.save(sync_to_sql=False)
        with templog() as log, patch.object(transaction, "atomic", atomic_check):
            call_command('populate_repeatrecords', log_path=log.path)
            self.assertNotIn('has differences:', log.content)
        obj = SQLRepeatRecord.objects.get(couch_id=doc._id)
        self.assertEqual(obj.registered_at, datetime(1970, 1, 1))

    def test_migrate_record_with_unsynced_sql_attempts(self):
        doc, _ = self.create_repeat_record(unwrap_doc=False)
        doc.save()  # sync to SQL, but do not save attempts
        with templog() as log, patch.object(transaction, "atomic", atomic_check):
            call_command('populate_repeatrecords', log_path=log.path)
            self.assertNotIn('has differences:', log.content)
        obj = SQLRepeatRecord.objects.get(couch_id=doc._id)
        self.assertEqual(len(obj.attempts), len(doc.attempts))
        self.assertTrue(obj.attempts)

    def test_migrate_record_with_partial_sql_attempts(self):
        doc, _ = self.create_repeat_record(unwrap_doc=False)
        doc.save()  # sync to SQL, but do not save attempts
        # This attempt is saved in both Couch and SQL, which means there
        # are three attempts in Couch and only one in SQL.
        doc.add_attempt(RepeatRecordAttempt(
            datetime=datetime.utcnow(),
            success_response="good call",
            succeeded=True,
        ))
        doc.save()  # sync to SQL, but do not save attempts
        assert len(doc.attempts) == 3, doc.attempts
        with templog() as log, patch.object(transaction, "atomic", atomic_check):
            call_command('populate_repeatrecords', log_path=log.path)
            self.assertNotIn('has differences:', log.content)
        obj = SQLRepeatRecord.objects.get(couch_id=doc._id)
        self.assertEqual(len(obj.attempts), 3)

    def test_migrate_record_with_no_attempts(self):
        doc, _ = self.create_repeat_record()
        doc.pop("attempts")
        doc_id = self.db.save_doc(doc)["id"]
        with templog() as log, patch.object(transaction, "atomic", atomic_check):
            call_command('populate_repeatrecords', log_path=log.path)
            self.assertNotIn('has differences:', log.content)
        obj = SQLRepeatRecord.objects.get(couch_id=doc_id)
        self.assertFalse(obj.attempts)

    def test_migrate_record_erroneous_next_check(self):
        doc, _ = self.create_repeat_record()
        doc.update(succeeded=True, next_check=datetime.utcnow().isoformat() + 'Z')
        doc_id = self.db.save_doc(doc)["id"]
        with templog() as log, patch.object(transaction, "atomic", atomic_check):
            call_command('populate_repeatrecords', log_path=log.path)
            self.assertNotIn('has differences:', log.content)
        obj = SQLRepeatRecord.objects.get(couch_id=doc_id)
        self.assertIsNone(obj.next_check)

    def test_migration_with_repeater_added_after_start(self):
        doc, obj = self.create_repeat_record(unwrap_doc=False)
        repeater3 = models.FormRepeater(
            id=UUID(REPEATER_ID_3),
            domain="test",
            connection_settings_id=self.repeater1.connection_settings_id,
            include_app_id_param=False,
        )
        repeater3.save()
        doc.repeater_id = repeater3.repeater_id
        doc.save(sync_attempts=True)
        with (
            templog() as log,
            patch.object(Command, "get_ids_to_ignore", lambda *a: {}),
            patch.object(transaction, "atomic", atomic_check),
        ):
            call_command('populate_repeatrecords', log_path=log.path)
            assert not log.content, log.content  # doc should have been implicitly ignored (already migrated)

    def test_migrate_domain(self):
        with patch.object(self.repeater2, "domain", "other"), templog() as log:
            docs = {}
            for repeater in [self.repeater1, self.repeater2]:
                doc, obj = self.create_repeat_record(unwrap_doc=False, repeater=repeater)
                doc.save(sync_to_sql=False)
                docs[repeater.domain] = doc

            call_command('populate_repeatrecords', domains=["other"], log_path=log.path)
            self.assertIn(f'Created model for RepeatRecord with id {docs["other"]._id}\n', log.content)
            self.assertNotIn(docs["test"]._id, log.content)
            SQLRepeatRecord.objects.get(couch_id=docs["other"]._id)
            with self.assertRaises(SQLRepeatRecord.DoesNotExist):
                SQLRepeatRecord.objects.get(couch_id=docs["test"]._id)

    def test_verify_record_missing_fields(self):
        doc, _ = self.create_repeat_record(unwrap_doc=False)
        doc.succeeded = True
        doc.save()
        self.db.save_doc({
            "_id": doc._id,
            "_rev": doc._rev,
            "doc_type": "RepeatRecord",
            "domain": "test",
            "last_checked": "2015-02-20T13:25:25.655650Z",
            "lock_date": None,
            "next_check": None,
            "payload_id": "00a7d361-474d-4cf3-9aed-f6204c2a0897",
            "repeater_id": self.repeater1.id.hex,
            "succeeded": True,
        })
        with templog() as log, patch.object(transaction, "atomic", atomic_check):
            call_command('populate_repeatrecords', log_path=log.path)
            self.assertIn('has differences:', log.content)

    def diff(self, doc, obj):
        return do_diff(Command, doc, obj)


def do_diff(Command, doc, obj):
    result = Command.diff_couch_and_sql(doc, obj)
    return [x for x in result if x is not None]


@contextmanager
def atomic_check(using=None, savepoint='ignored'):
    with _atomic(using=using):
        yield
        connection.check_constraints()


_atomic = transaction.atomic


@contextmanager
def templog():
    with tempdir() as tmp:
        yield Log(tmp)


class Log:
    def __init__(self, tmp):
        self.path = Path(tmp) / "log.txt"

    @cached_property
    def content(self):
        with self.path.open() as lines:
            return "".join(lines)
