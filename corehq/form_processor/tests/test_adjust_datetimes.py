from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import SimpleTestCase
from corehq.apps.tzmigration.api import phone_timezones_should_be_processed
from corehq.apps.tzmigration.test_utils import \
    run_pre_and_post_timezone_migration
from corehq.form_processor.utils import adjust_datetimes


class AdjustDatetimesTest(SimpleTestCase):

    def test_date_no_change(self):
        self.assertEqual(adjust_datetimes({'date': '2015-04-03'}),
                         {'date': '2015-04-03'})

    def test_no_tz(self):
        self.assertEqual(
            adjust_datetimes({'datetime': '2013-03-09T06:30:09.007'}),
            {'datetime': '2013-03-09T06:30:09.007000Z'}
        )

    @run_pre_and_post_timezone_migration
    def test_strip_tz(self):
        if phone_timezones_should_be_processed():
            self.assertEqual(
                adjust_datetimes({'datetime': '2013-03-09T06:30:09.007+03'}),
                {'datetime': '2013-03-09T03:30:09.007000Z'}
            )
        else:
            self.assertEqual(
                adjust_datetimes({'datetime': '2013-03-09T06:30:09.007+03'}),
                {'datetime': '2013-03-09T06:30:09.007000Z'}
            )

    def test_match_no_parse(self):
        fake_datetime = '2015-07-14 2015-06-07 '
        self.assertEqual(
            adjust_datetimes({'fake_datetime': fake_datetime}),
            {'fake_datetime': fake_datetime}
        )
