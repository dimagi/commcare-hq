from datetime import datetime

from django.test import TestCase

import pytz

from corehq.motech.models import ConnectionSettings

from ..const import RECORD_SUCCESS_STATE
from ..models import (
    FormRepeater,
    RepeatRecord,
    RepeatRecordAttempt,
    SQLRepeater,
)
from ..views.repeat_record_display import RepeatRecordDisplay
from .test_models import make_repeat_record

DOMAIN = 'test-domain-display'


class RepeaterTestCase(TestCase):

    def setUp(self):
        super().setUp()
        self.url = 'https://www.example.com/api/'
        conn = ConnectionSettings.objects.create(domain=DOMAIN, name=self.url, url=self.url)
        self.repeater = FormRepeater(
            domain=DOMAIN,
            url=self.url,
            connection_settings_id=conn.id,
            include_app_id_param=False
        )
        self.repeater.save()
        self.date_format = "%Y-%m-%d %H:%M:%S"
        self.last_checked_str = "2022-01-12 09:04:15"
        self.next_check_str = "2022-01-12 11:04:15"
        self.last_checked = datetime.strptime(self.last_checked_str, self.date_format)
        self.next_check = datetime.strptime(self.next_check_str, self.date_format)
        self.sql_repeater = SQLRepeater.objects.get(repeater_id=self.repeater.get_id)
        self.sql_repeater.next_attempt_at = self.next_check
        self.sql_repeater.last_attempt_at = self.last_checked
        self.sql_repeater.save()

    def tearDown(self):
        self.repeater.delete()
        super().tearDown()

    def test_record_display_couch(self):
        record = RepeatRecord(
            _id='record_id_123',
            domain=DOMAIN,
            succeeded=True,
            repeater_id=self.repeater.get_id,
            last_checked=self.last_checked,
            next_check=self.next_check,
            payload_id='123',
        )
        record.attempts.append(
            RepeatRecordAttempt(
                cancelled=False,
                datetime=self.last_checked,
                failure_reason=None,
                success_response="",
                next_check=None,
                succeeded=True,
                info=None,
            )
        )
        self._check_display(record)

    def test_record_display_sql(self):
        with make_repeat_record(self.sql_repeater, RECORD_SUCCESS_STATE) as record:
            record.sqlrepeatrecordattempt_set.create(
                state=RECORD_SUCCESS_STATE,
                message='',
            )
            self._check_display(record)

    def _check_display(self, record):
        display = RepeatRecordDisplay(record, pytz.UTC, date_format=self.date_format)
        self.assertEqual(display.record_id, record.record_id)
        self.assertEqual(display.last_checked, self.last_checked_str)
        self.assertEqual(display.next_attempt_at, self.next_check_str)
        self.assertEqual(display.url, self.url)
        self.assertEqual(display.state, '<span class="label label-success">Success</span>')
        self.assertHTMLEqual(display.attempts, """
            <ul class="list-unstyled">
                <li><strong>Attempt #1</strong>
                    <br/><i class="fa fa-check"></i> Success
                </li>
            </ul>""")
