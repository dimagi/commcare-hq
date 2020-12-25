from contextlib import contextmanager
from datetime import timedelta
from uuid import uuid4

from django.conf import settings
from django.test import TestCase
from django.utils import timezone

from nose.tools import assert_in

from corehq.motech.const import BASIC_AUTH
from corehq.motech.models import ConnectionSettings

from ..const import (
    RECORD_CANCELLED_STATE,
    RECORD_FAILURE_STATE,
    RECORD_PENDING_STATE,
    RECORD_SUCCESS_STATE,
)
from ..models import FormRepeater, SQLRepeaterStub, get_all_repeater_types
from ..repeater_generators import FormRepeaterXMLPayloadGenerator


def test_get_all_repeater_types():
    types = get_all_repeater_types()
    for cls in settings.REPEATER_CLASSES:
        name = cls.split('.')[-1]
        assert_in(name, types)


class RepeaterConnectionSettingsTests(TestCase):

    def setUp(self):
        self.rep = FormRepeater(
            domain="greasy-spoon",
            url="https://spam.example.com/api/",
            auth_type=BASIC_AUTH,
            username="terry",
            password="Don't save me decrypted!",
            notify_addresses_str="admin@example.com",
            format=FormRepeaterXMLPayloadGenerator.format_name,
        )

    def tearDown(self):
        if self.rep.connection_settings_id:
            ConnectionSettings.objects.filter(
                pk=self.rep.connection_settings_id
            ).delete()
        self.rep.delete()

    def test_create_connection_settings(self):
        self.assertIsNone(self.rep.connection_settings_id)
        conn = self.rep.connection_settings

        self.assertIsNotNone(self.rep.connection_settings_id)
        self.assertEqual(conn.name, self.rep.url)
        self.assertEqual(self.rep.plaintext_password, conn.plaintext_password)
        # rep.password was saved decrypted; conn.password is not:
        self.assertNotEqual(self.rep.password, conn.password)


class TestSQLRepeatRecordOrdering(TestCase):

    def setUp(self):
        self.couch_repeater = FormRepeater(
            domain='eden',
            url='https://spam.example.com/api/',
        )
        self.couch_repeater.save()
        self.sql_repeater = SQLRepeaterStub.objects.create(
            domain='eden',
            couch_id=self.couch_repeater.get_id,
        )
        self.sql_repeater.repeat_records.create(
            domain=self.sql_repeater.domain,
            payload_id='eve',
            registered_at='1970-02-01',
        )

    def tearDown(self):
        self.sql_repeater.delete()
        self.couch_repeater.delete()

    def test_earlier_record_created_later(self):
        self.sql_repeater.repeat_records.create(
            domain=self.sql_repeater.domain,
            payload_id='lilith',
            # If Unix time starts on 1970-01-01, then I guess 1970-01-06
            # is Unix Rosh Hashanah, the sixth day of Creation, the day
            # [Lilith][1] and Adam were created from clay.
            # [1] https://en.wikipedia.org/wiki/Lilith
            registered_at='1970-01-06',
        )
        repeat_records = self.sql_repeater.repeat_records.all()
        self.assertEqual(repeat_records[0].payload_id, 'lilith')
        self.assertEqual(repeat_records[1].payload_id, 'eve')

    def test_later_record_created_later(self):
        self.sql_repeater.repeat_records.create(
            domain=self.sql_repeater.domain,
            payload_id='cain',
            registered_at='1995-01-06',
        )
        repeat_records = self.sql_repeater.repeat_records.all()
        self.assertEqual(repeat_records[0].payload_id, 'eve')
        self.assertEqual(repeat_records[1].payload_id, 'cain')


class RepeaterManagerTests(TestCase):

    def setUp(self):
        self.couch_repeater = FormRepeater(
            domain="greasy-spoon",
            url="https://spam.example.com/api/",
        )
        self.couch_repeater.save()
        self.sql_repeater = SQLRepeaterStub.objects.create(
            domain="greasy-spoon",
            couch_id=self.couch_repeater.get_id,
        )

    def tearDown(self):
        self.sql_repeater.delete()
        self.couch_repeater.delete()

    def test_all_ready_no_repeat_records(self):
        sql_repeaters = SQLRepeaterStub.objects.all_ready()
        self.assertEqual(len(sql_repeaters), 0)

    def test_all_ready_pending_repeat_record(self):
        with make_repeat_record(self.sql_repeater, RECORD_PENDING_STATE):
            sql_repeaters = SQLRepeaterStub.objects.all_ready()
            self.assertEqual(len(sql_repeaters), 1)
            self.assertEqual(sql_repeaters[0].id, self.sql_repeater.id)

    def test_all_ready_failed_repeat_record(self):
        with make_repeat_record(self.sql_repeater, RECORD_FAILURE_STATE):
            sql_repeaters = SQLRepeaterStub.objects.all_ready()
            self.assertEqual(len(sql_repeaters), 1)
            self.assertEqual(sql_repeaters[0].id, self.sql_repeater.id)

    def test_all_ready_succeeded_repeat_record(self):
        with make_repeat_record(self.sql_repeater, RECORD_SUCCESS_STATE):
            sql_repeaters = SQLRepeaterStub.objects.all_ready()
            self.assertEqual(len(sql_repeaters), 0)

    def test_all_ready_cancelled_repeat_record(self):
        with make_repeat_record(self.sql_repeater, RECORD_CANCELLED_STATE):
            sql_repeaters = SQLRepeaterStub.objects.all_ready()
            self.assertEqual(len(sql_repeaters), 0)

    def test_all_ready_paused(self):
        with make_repeat_record(self.sql_repeater, RECORD_PENDING_STATE), \
                pause_repeater(self.sql_repeater):
            sql_repeaters = SQLRepeaterStub.objects.all_ready()
            self.assertEqual(len(sql_repeaters), 0)

    def test_all_ready_next_future(self):
        in_five_mins = timezone.now() + timedelta(minutes=5)
        with make_repeat_record(self.sql_repeater, RECORD_PENDING_STATE), \
                set_next_attempt_at(self.sql_repeater, in_five_mins):
            sql_repeaters = SQLRepeaterStub.objects.all_ready()
            self.assertEqual(len(sql_repeaters), 0)

    def test_all_ready_next_past(self):
        five_mins_ago = timezone.now() - timedelta(minutes=5)
        with make_repeat_record(self.sql_repeater, RECORD_PENDING_STATE), \
                set_next_attempt_at(self.sql_repeater, five_mins_ago):
            sql_repeaters = SQLRepeaterStub.objects.all_ready()
            self.assertEqual(len(sql_repeaters), 1)
            self.assertEqual(sql_repeaters[0].id, self.sql_repeater.id)


@contextmanager
def make_repeat_record(sql_repeater, state):
    repeat_record = sql_repeater.repeat_records.create(
        domain=sql_repeater.domain,
        payload_id=str(uuid4()),
        state=state,
        registered_at=timezone.now()
    )
    try:
        yield repeat_record
    finally:
        repeat_record.delete()


@contextmanager
def pause_repeater(sql_repeater):
    sql_repeater.is_paused = True
    sql_repeater.save()
    try:
        yield
    finally:
        sql_repeater.is_paused = False
        sql_repeater.save()


@contextmanager
def set_next_attempt_at(sql_repeater, when):
    sql_repeater.next_attempt_at = when
    sql_repeater.save()
    try:
        yield
    finally:
        sql_repeater.next_attempt_at = None
        sql_repeater.save()
