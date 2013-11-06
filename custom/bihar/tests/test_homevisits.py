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

        self.assertIndicatorsEmpty(indicator)


    def testBPAllInFirstTri(self):
        indicator = CareBiharFluff()

        dates = {
            'bp1_due': '2013-01-21', 'bp1_done': '2013-01-21', 'bp1_days_overdue': '0',
            'bp2_due': '2013-01-22', 'bp2_done': '2013-01-22', 'bp2_days_overdue': '0',
            'bp3_due': '2013-01-23', 'bp3_done': '2013-01-23', 'bp3_days_overdue': '0',
        }
        case = self._load_case('test_bihar_bp.json', dates)
        indicator.calculate(case)
        self.assertIndicatorsEmpty(indicator, vals=('bp2', 'bp3', 'pnc', 'ebf', 'cf'))

    def testBPAllInSecondTri(self):
        indicator = CareBiharFluff()

        dates = {
            'bp1_due': '2013-03-21', 'bp1_done': '2013-03-21', 'bp1_days_overdue': '0',
            'bp2_due': '2013-03-22', 'bp2_done': '2013-03-22', 'bp2_days_overdue': '0',
            'bp3_due': '2013-03-23', 'bp3_done': '2013-03-23', 'bp3_days_overdue': '0',
        }
        case = self._load_case('test_bihar_bp.json', dates)
        indicator.calculate(case)
        bp2 = indicator.bp2
        self.assertEqual(3, len(bp2['total']))
        [v1, v2, v3] = bp2['total']
        self.assertEqual(date(2013, 3, 21), v1['date'])
        self.assertEqual(date(2013, 3, 22), v2['date'])
        self.assertEqual(date(2013, 3, 23), v3['date'])
        for res in bp2['total']:
            self.assertEqual(1, res['value'])

        self.assertEqual(3, len(bp2['numerator']))
        [v1, v2, v3] = bp2['numerator']
        self.assertEqual(date(2013, 3, 21), v1['date'])
        self.assertEqual(date(2013, 3, 22), v2['date'])
        self.assertEqual(date(2013, 3, 23), v3['date'])
        for res in bp2['total']:
            self.assertEqual(1, res['value'])

        self.assertIndicatorsEmpty(indicator, vals=('bp3', 'pnc', 'ebf', 'cf'))

    def testBPAllInThirdTri(self):
        indicator = CareBiharFluff()

        dates = {
            'bp1_due': '2013-06-21', 'bp1_done': '2013-06-21', 'bp1_days_overdue': '0',
            'bp2_due': '2013-06-22', 'bp2_done': '2013-06-22', 'bp2_days_overdue': '0',
            'bp3_due': '2013-06-23', 'bp3_done': '2013-06-23', 'bp3_days_overdue': '0',
        }
        case = self._load_case('test_bihar_bp.json', dates)
        indicator.calculate(case)
        bp3 = indicator.bp3
        self.assertEqual(3, len(bp3['total']))
        [v1, v2, v3] = bp3['total']
        self.assertEqual(date(2013, 6, 21), v1['date'])
        self.assertEqual(date(2013, 6, 22), v2['date'])
        self.assertEqual(date(2013, 6, 23), v3['date'])
        for res in bp3['total']:
            self.assertEqual(1, res['value'])

        self.assertEqual(3, len(bp3['numerator']))
        [v1, v2, v3] = bp3['numerator']
        self.assertEqual(date(2013, 6, 21), v1['date'])
        self.assertEqual(date(2013, 6, 22), v2['date'])
        self.assertEqual(date(2013, 6, 23), v3['date'])
        for res in bp3['total']:
            self.assertEqual(1, res['value'])

        self.assertIndicatorsEmpty(indicator, vals=('bp2', 'pnc', 'ebf', 'cf'))

    def testVisitBounds(self):
        # test dates around the +/- 10 day window and make sure they are/aren't counted
        out_of_bounds = ['2013-03-11', '2013-04-04']
        for oob in out_of_bounds:
            indicator = CareBiharFluff()
            dates = {
                'bp1_due': '2013-01-22', 'bp1_done': '2013-01-22', 'bp1_days_overdue': '0',
                'bp2_due': '2013-03-22', 'bp2_done': oob, 'bp2_days_overdue': '0',
                'bp3_due': '2013-06-22', 'bp3_done': '2013-06-22', 'bp3_days_overdue': '0',
            }
            case = self._load_case('test_bihar_bp.json', dates)
            indicator.calculate(case)
            bp2 = indicator.bp2
            [total] = bp2['total']
            self.assertEqual(date(2013, 3, 22), total['date'])
            self.assertEqual(1, total['value'])
            self.assertEqual(0, len(bp2['numerator']))

        in_bounds = ['2013-03-13', '2013-04-01']
        for ib in in_bounds:
            indicator = CareBiharFluff()
            dates = {
                'bp1_due': '2013-01-22', 'bp1_done': '2013-01-22', 'bp1_days_overdue': '0',
                'bp2_due': '2013-03-22', 'bp2_done': ib, 'bp2_days_overdue': '0',
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

    def assertIndicatorsEmpty(self, indicator, vals=None):
        vals = vals or ('pnc', 'ebf', 'cf')
        for attr in vals:
            results = getattr(indicator, attr)
            self.assertEqual(0, len(results['total']))
            self.assertEqual(0, len(results['numerator']))

    def _load_case(self, filename, format_dict=None):
        format_dict = format_dict or {}
        fullpath = os.path.join(os.path.dirname(__file__), 'data', 'cases', filename)
        with open(fullpath, 'r') as f:
            raw = f.read()
            formatted = raw % format_dict
            return BiharCase.from_dump(json.loads(formatted))



