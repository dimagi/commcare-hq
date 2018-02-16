from __future__ import absolute_import
from datetime import date
from custom.world_vision.models import WorldVisionChildFluff
from custom.world_vision.tests.utils import WVTest


class TestChildFluff(WVTest):
    file_name = 'test_child_case.json'

    def testCalculators(self):
        indicator = WorldVisionChildFluff()
        indicator.calculate(self.case)
        women_registered = indicator.women_registered['total'][0]
        self.assertEqual(1, women_registered['value'])
        self.assertEqual(date(2014, 2, 3), women_registered['date'])
