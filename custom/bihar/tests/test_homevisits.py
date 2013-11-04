from datetime import date
import json
import os
from django.test import TestCase
from custom.bihar.models import BiharCase, CareBiharFluff


class TestHomeVisits(TestCase):

    def testBPNormal(self):
        # our mother has the following date properties set
        # EDD: 2013-08-19
        # 3rd Tri: 2013-05-17
        # 2nd Tri: 2013-02-13
        indicator = CareBiharFluff()

        # everything perfect
        dates = {
            'bp1_due': '2013-01-22', 'bp1_done': '2013-01-22', 'bp1_days_overdue': '0',
            'bp2_due': '2013-03-22', 'bp2_done': '2013-03-22', 'bp2_days_overdue': '0',
            'bp3_due': '2013-06-22', 'bp3_done': '2013-06-22', 'bp3_days_overdue': '0',
        }
        case = self._load_case('test_bihar_bp.json', dates)
        indicator.calculate(case)
        bp2 = indicator.bp2
        [total] = bp2['total']
        self.assertEqual(date(2013, 3, 22), total['date'])
        self.assertEqual(1, total['value'])

        [numerator] = bp2['numerator']
        self.assertEqual(date(2013, 3, 22), numerator['date'])
        self.assertEqual(1, numerator['value'])

        bp3 = indicator.bp3
        self.assertEqual(1, len(bp3['total']))
        [total] = bp3['total']
        self.assertEqual(date(2013, 6, 22), total['date'])
        self.assertEqual(1, total['value'])
        [numerator] = bp3['numerator']
        self.assertEqual(date(2013, 6, 22), numerator['date'])
        self.assertEqual(1, numerator['value'])

    def _load_case(self, filename, format_dict=None):
        format_dict = format_dict or {}
        fullpath = os.path.join(os.path.dirname(__file__), 'data', 'cases', filename)
        with open(fullpath, 'r') as f:
            raw = f.read()
            formatted = raw % format_dict
            return BiharCase.from_dump(json.loads(formatted))



