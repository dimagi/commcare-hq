import datetime
import dateutil.parser
from django.test import SimpleTestCase
import pytz
from corehq.apps.tzmigration import phone_timezones_have_been_processed
from corehq.const import USER_DATETIME_FORMAT
from corehq.util.timezones.conversions import ServerTime, PhoneTime, \
    UserTime
from dimagi.utils.dates import safe_strftime
from corehq.apps.tzmigration.test_utils import \
    run_pre_and_post_timezone_migration


class UIStringTest(SimpleTestCase):
    def test_ui_string(self):
        now = datetime.datetime.utcnow()
        user_time = ServerTime(now).user_time(pytz.FixedOffset(-4 * 60))
        self.assertEqual(user_time.ui_string(),
                         user_time.done().strftime(USER_DATETIME_FORMAT))

    def test_safe_strftime(self):
        dt = datetime.datetime(2015, 1, 1, 12, 24, 48)
        self.assertEqual(safe_strftime(dt, '%Y-%m-%dT%H:%M:%SZ'),
                         '2015-01-01T12:24:48Z')

    def test_safe_strftime_abbr_year(self):
        dt = datetime.datetime(2015, 1, 1, 12, 24, 48)
        self.assertEqual(safe_strftime(dt, '%y-%m-%dT%H:%M:%SZ'),
                         '15-01-01T12:24:48Z')


class TimezoneConversionTest(SimpleTestCase):
    def test_server_to_user(self):
        cases = [
            ('2015-03-20T12:00:00', pytz.FixedOffset(-4 * 60),
             '2015-03-20T08:00:00-04:00'),
            ('2015-03-21T00:30:00', pytz.FixedOffset(-4 * 60),
             '2015-03-20T20:30:00-04:00'),
        ]
        for in_, tz, out in cases:
            server_dt = dateutil.parser.parse(in_)
            user_dt = ServerTime(server_dt).user_time(tz).done()
            self.assertEqual(user_dt.isoformat(), out)

    def test_user_to_server(self):
        cases = [
            ('2015-03-20T08:00:00', pytz.FixedOffset(-4 * 60),
             '2015-03-20T12:00:00'),
            ('2015-03-20T20:30:00', pytz.FixedOffset(-4 * 60),
             '2015-03-21T00:30:00'),
        ]
        for in_, tz, out in cases:
            user_dt = dateutil.parser.parse(in_)
            server_dt = UserTime(user_dt, tz).server_time().done()
            self.assertEqual(server_dt.isoformat(), out)

    @run_pre_and_post_timezone_migration
    def test_server_to_phone(self):
        cases = [
            ('2015-03-20T12:00:00', pytz.FixedOffset(-4 * 60),
             '2015-03-20T08:00:00'),
            ('2015-03-21T00:30:00', pytz.FixedOffset(-4 * 60),
             '2015-03-20T20:30:00'),
        ]
        for in_, tz, out in cases:
            server_dt = dateutil.parser.parse(in_)
            phone_dt = ServerTime(server_dt).phone_time(tz).done()
            if phone_timezones_have_been_processed():
                # no change
                self.assertEqual(phone_dt.isoformat(), in_)
            else:
                self.assertEqual(phone_dt.isoformat(), out)

    @run_pre_and_post_timezone_migration
    def test_phone_to_server(self):
        cases = [
            ('2015-03-20T08:00:00', pytz.FixedOffset(-4 * 60),
             '2015-03-20T12:00:00'),
            ('2015-03-20T20:30:00', pytz.FixedOffset(-4 * 60),
             '2015-03-21T00:30:00'),
        ]
        for in_, tz, out in cases:
            phone_dt = dateutil.parser.parse(in_)
            server_dt = PhoneTime(phone_dt, tz).server_time().done()
            if phone_timezones_have_been_processed():
                # no change
                self.assertEqual(server_dt.isoformat(), in_)
            else:
                self.assertEqual(server_dt.isoformat(), out)


class CloudCareTimeTest(SimpleTestCase):
    def test_utc_phonetime(self):
        dt = datetime.datetime.utcnow()
        self.assertEqual(PhoneTime(dt, pytz.UTC)
                         .user_time(pytz.FixedOffset(9 * 60 + 30)).done(),
                         ServerTime(dt)
                         .user_time(pytz.FixedOffset(9 * 60 + 30)).done())
