from datetime import datetime

from django.test import TestCase

import pytz

from corehq.motech.models import ConnectionSettings

from ..const import RECORD_SUCCESS_STATE
from ..models import (
    FormRepeater,
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
            connection_settings_id=conn.id,
            include_app_id_param=False,
        )
        self.repeater.save()
        self.date_format = "%Y-%m-%d %H:%M:%S"
        self.last_checked_str = "2022-01-12 09:04:15"
        self.next_check_str = "2022-01-12 11:04:15"
        self.last_checked = datetime.strptime(self.last_checked_str, self.date_format)
        self.next_check = datetime.strptime(self.next_check_str, self.date_format)
        self.repeater.next_attempt_at = self.next_check
        self.repeater.last_attempt_at = self.last_checked
        self.repeater.save()

    def test_record_display_sql(self):
        with make_repeat_record(self.repeater, RECORD_SUCCESS_STATE) as record:
            record.attempt_set.create(state=RECORD_SUCCESS_STATE)
            self._check_display(record)

    def _check_display(self, record):
        display = RepeatRecordDisplay(record, pytz.UTC, date_format=self.date_format)
        self.assertEqual(display.record_id, record.record_id)
        self.assertEqual(display.last_checked, self.last_checked_str)
        self.assertEqual(display.next_attempt_at, self.next_check_str)
        self.assertEqual(display.url, self.url)
        self.assertEqual(display.state, '<span class="label label-success">Success</span>')
