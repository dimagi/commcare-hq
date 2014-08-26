from django.test import TestCase
from corehq.apps.reports.views import calculate_hour, recalculate_hour, calculate_day


class TimeAndDateManipulationTest(TestCase):
    def calculate_hour_test(self):
        self.assertTrue((12, 0), calculate_hour(10, 2, 0))
        self.assertTrue((8, 0), calculate_hour(10, -2, 0))
        self.assertTrue((12, 0), calculate_hour(10, 2, 30))
        self.assertTrue((7, 0), calculate_hour(10, -2, 30))
        self.assertTrue((22, -1), calculate_hour(3, -5, 0))
        self.assertTrue((3, 1), calculate_hour(22, 5, 0))
        self.assertRaises(AssertionError, calculate_hour(25, 0, 0))

    def recalculate_hour_test(self):
        self.assertTrue((10, 0), recalculate_hour(12, 2, 0))
        self.assertTrue((10, 0), recalculate_hour(8, -2, 0))
        self.assertTrue((10, 0), recalculate_hour(12, 2, 30))
        self.assertTrue((10, 0), recalculate_hour(7, -2, 30))
        self.assertTrue((3, 1), recalculate_hour(22, -5, 0))
        self.assertTrue((22, -1), recalculate_hour(3, 5, 0))

    def calculate_day_test(self):
        self.assertTrue(1, calculate_day('weekly', 1, 0))
        self.assertTrue(1, calculate_day('monthly', 1, 0))
        self.assertTrue(5, calculate_day('weekly', 6, -1))
        self.assertTrue(5, calculate_day('monthly', 6, -1))
        self.assertTrue(6, calculate_day('monthly', 5, 1))
        self.assertTrue(6, calculate_day('monthly', 5, 1))
        self.assertTrue(6, calculate_day('weekly', 1, -1))
        self.assertTrue(31, calculate_day('monthly', 1, -1))
        self.assertTrue(0, calculate_day('weekly', 6, 1))
        self.assertTrue(1, calculate_day('monthly', 31, 1))


