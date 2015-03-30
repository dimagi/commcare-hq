import dateutil.parser
from django.test import SimpleTestCase
import pytz
from corehq.util.timezones.conversions import ServerTime, \
    TIMEZONE_DATA_MIGRATION_COMPLETE, PhoneTime, UserTime


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
            if TIMEZONE_DATA_MIGRATION_COMPLETE:
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
            if TIMEZONE_DATA_MIGRATION_COMPLETE:
                server_dt = phone_dt
            else:
                server_dt = PhoneTime(phone_dt, tz).server_time().done()
            self.assertEqual(server_dt.isoformat(), out)
