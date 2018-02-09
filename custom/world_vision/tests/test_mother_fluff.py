from __future__ import absolute_import
from datetime import date
from custom.world_vision.models import WorldVisionMotherFluff
from custom.world_vision.tests.utils import WVTest


class TestMotherFluff(WVTest):

    file_name = 'test_mother_case.json'

    def testCalculators(self):
        indicator = WorldVisionMotherFluff()
        indicator.calculate(self.case)

        number_of_childern = indicator.number_of_children['total'][0]
        self.assertEqual(0, number_of_childern['value'])
        self.assertEqual(date(2014, 5, 16), number_of_childern['date'])

        number_of_boys = indicator.number_of_boys['total'][0]
        self.assertEqual(0, number_of_boys['value'])
        self.assertEqual(date(2014, 5, 16), number_of_boys['date'])

        number_of_girls = indicator.number_of_girls['total'][0]
        self.assertEqual(0, number_of_girls['value'])
        self.assertEqual(date(2014, 5, 16), number_of_girls['date'])

        number_of_children_born_dead = indicator.number_of_children_born_dead['total'][0]
        self.assertEqual(0, number_of_children_born_dead['value'])
        self.assertEqual(date(2014, 5, 16), number_of_children_born_dead['date'])

        women_registered = indicator.women_registered['total'][0]
        self.assertEqual(1, women_registered['value'])
        self.assertEqual(date(2014, 5, 16), women_registered['date'])
