from datetime import datetime
from django.test.testcases import SimpleTestCase

from custom.ewsghana.utils import calculate_last_period


class TestCalculateLastPeriod(SimpleTestCase):

    def test_calculation(self):
        monday = datetime(2016, 1, 11)
        tuesday = datetime(2016, 1, 12)
        wednesday = datetime(2016, 1, 13)
        thurdsay = datetime(2016, 1, 14)
        friday = datetime(2016, 1, 15)
        saturday = datetime(2016, 1, 16)
        sunday = datetime(2016, 1, 17)

        expected_period = (datetime(2016, 1, 8), datetime(2016, 1, 14, 23, 59, 59, 999999))

        self.assertEqual(calculate_last_period(monday), expected_period)
        self.assertEqual(calculate_last_period(tuesday), expected_period)
        self.assertEqual(calculate_last_period(wednesday), expected_period)
        self.assertEqual(calculate_last_period(thurdsay), expected_period)

        expected_period = (datetime(2016, 1, 15), datetime(2016, 1, 21, 23, 59, 59, 999999))

        self.assertEqual(calculate_last_period(friday), expected_period)
        self.assertEqual(calculate_last_period(saturday), expected_period)
        self.assertEqual(calculate_last_period(sunday), expected_period)
