import datetime
import dateutil.parser
from django.test import SimpleTestCase
import pytz
from corehq.const import USER_DATETIME_FORMAT
from corehq.util.timezones.conversions import ServerTime, PhoneTime, \
    UserTime, get_timezone_data_migration_complete
from dimagi.utils.dates import safe_strftime


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

    def test_server_to_phone(self):
        cases = [
            ('2015-03-20T12:00:00', pytz.FixedOffset(-4 * 60),
             '2015-03-20T08:00:00'),
            ('2015-03-21T00:30:00', pytz.FixedOffset(-4 * 60),
             '2015-03-20T20:30:00'),
        ]
        for in_, tz, out in cases:
            server_dt = dateutil.parser.parse(in_)
            if get_timezone_data_migration_complete():
                phone_dt = server_dt
            else:
                phone_dt = ServerTime(server_dt).phone_time(tz).done()
            self.assertEqual(phone_dt.isoformat(), out)

    def test_phone_to_server(self):
        cases = [
            ('2015-03-20T08:00:00', pytz.FixedOffset(-4 * 60),
             '2015-03-20T12:00:00'),
            ('2015-03-20T20:30:00', pytz.FixedOffset(-4 * 60),
             '2015-03-21T00:30:00'),
        ]
        for in_, tz, out in cases:
            phone_dt = dateutil.parser.parse(in_)
            if get_timezone_data_migration_complete():
                server_dt = phone_dt
            else:
                server_dt = PhoneTime(phone_dt, tz).server_time().done()
            self.assertEqual(server_dt.isoformat(), out)


class CloudCareTimeTest(SimpleTestCase):
    def test_utc_phonetime(self):
        dt = datetime.datetime.utcnow()
        self.assertEqual(PhoneTime(dt, pytz.UTC)
                         .user_time(pytz.FixedOffset(9 * 60 + 30)).done(),
                         ServerTime(dt)
                         .user_time(pytz.FixedOffset(9 * 60 + 30)).done())
