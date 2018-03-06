from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import datetime

from django.test import SimpleTestCase

from corehq.apps.userreports.tasks import time_in_range
from six.moves import range


TEST_SETTINGS = {
    '*': [(0, 4), (12, 23)],
    7: [(0, 23)]
}


class TimeInRange(SimpleTestCase):

    def test_sunday_all_day(self):
        for hour in range(24):
            time = datetime(2018, 1, 21, hour)
            self.assertTrue(time_in_range(time, TEST_SETTINGS))

    def test_monday(self):
        for hour in range(0, 4):
            time = datetime(2018, 1, 22, hour)
            self.assertTrue(time_in_range(time, TEST_SETTINGS))

        for hour in range(5, 12):
            time = datetime(2018, 1, 22, hour)
            self.assertFalse(time_in_range(time, TEST_SETTINGS))

        for hour in range(12, 23):
            time = datetime(2018, 1, 22, hour)
            self.assertTrue(time_in_range(time, TEST_SETTINGS))
