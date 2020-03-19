from django.test import SimpleTestCase

from corehq.apps.groups.models import dt_no_Z_re


class DtNoZReTests(SimpleTestCase):
    def test_matches_seconds_no_z(self):
        matches = dt_no_Z_re.match("2019-11-25T09:26:19")
        self.assertIsNotNone(matches)

    def test_matches_milliseconds_no_z(self):
        matches = dt_no_Z_re.match("2019-11-25T09:26:19.357709")
        self.assertIsNotNone(matches)

    def test_not_matches_seconds_z(self):
        matches = dt_no_Z_re.match("2019-11-25T09:26:19Z")
        self.assertIsNone(matches)

    def test_not_matches_milliseconds_z(self):
        matches = dt_no_Z_re.match("2019-11-25T09:26:19.357709Z")
        self.assertIsNone(matches)

    def test_not_matches_seconds_tz(self):
        matches = dt_no_Z_re.match("2019-11-25T09:26:19+0530")
        self.assertIsNone(matches)

    def test_not_matches_milliseconds_tz(self):
        matches = dt_no_Z_re.match("2019-11-25T09:26:19.357709+0530")
        self.assertIsNone(matches)
