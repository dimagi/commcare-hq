from datetime import datetime

from django.test import TestCase

import pytz

from corehq.motech.models import ConnectionSettings

from ..const import State
from ..models import FormRepeater
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

    def test_record_display_sql(self):
        with make_repeat_record(self.repeater, State.Success) as record:
            response = ResponseDuck()
            record.add_success_attempt(response)
            last_checked = record.attempts[0].created_at
            self.last_checked_str = last_checked.strftime(self.date_format)

            display = RepeatRecordDisplay(record, pytz.UTC, date_format=self.date_format)
            self.assertEqual(display.record_id, record.id)
            self.assertEqual(display.last_checked, self.last_checked_str)
            self.assertEqual(display.next_check, '---')
            self.assertEqual(display.url, self.url)
            self.assertEqual(display.state, '<span class="label label-success">Success</span>')

    def test_record_display_process_repeaters(self):
        jan_1 = datetime.strptime('2025-01-01 00:00:00', self.date_format)
        self.repeater.next_attempt_at = jan_1
        with make_repeat_record(self.repeater, State.Pending) as record:
            display = RepeatRecordDisplay(
                record,
                pytz.UTC,
                date_format=self.date_format,
                process_repeaters_enabled=True,
            )
            self.assertEqual(display.next_check, '2025-01-01 00:00:00')

    def test_record_display_repeater_paused(self):
        self.repeater.is_paused = True
        with make_repeat_record(self.repeater, State.Pending) as record:
            display = RepeatRecordDisplay(record, pytz.UTC, date_format=self.date_format)
            self.assertEqual(display.next_check, 'Paused')


class ResponseDuck:
    status_code = 200
    reason = 'Success'
