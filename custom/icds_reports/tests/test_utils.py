from __future__ import absolute_import
from django.test import SimpleTestCase

from custom.icds_reports.utils import generate_data_for_map


class TestUtils(SimpleTestCase):

    def test_calculate_average(self):
        data_mock = [{'all': 9, 'children': 9, 'state_name': u'State 1', 'state_map_location_name': u'test1'},
                    {'all': 0, 'children': 0, 'state_name': u'State 2', 'state_map_location_name': u'test2'},
                    {'all': 0, 'children': 0, 'state_name': u'State 3', 'state_map_location_name': u'test3'},
                    {'all': 0, 'children': 0, 'state_name': u'State 4', 'state_map_location_name': u'test4'},
                    {'all': 6, 'children': 0, 'state_name': u'State 5', 'state_map_location_name': u'test5'}]
        data_for_map, valid_total, in_month_total, average = generate_data_for_map(
            data_mock,
            'state',
            'children',
            'all',
            20,
            60
        )
        self.assertEquals(average, 20.0)

    def test_calculate_average_if_one_location(self):
        data_mock = [{'all': 9, 'children': 9, 'state_name': u'State 1', 'state_map_location_name': u'test1'}]
        data_for_map, valid_total, in_month_total, average = generate_data_for_map(
            data_mock,
            'state',
            'children',
            'all',
            20,
            60
        )
        self.assertEquals(average, 100.0)

    def test_calculate_average_if_divide_by_zero(self):
        data_mock = [{'all': 0, 'children': 0, 'state_name': u'State 1', 'state_map_location_name': u'test1'}]
        data_for_map, valid_total, in_month_total, average = generate_data_for_map(
            data_mock,
            'state',
            'children',
            'all',
            20,
            60
        )
        self.assertEquals(average, 0.0)

    def test_calculate_average_if_data_are_none(self):
        data_mock = [{'all': None, 'children': None, 'state_name': None, 'state_map_location_name': None}]
        data_for_map, valid_total, in_month_total, average = generate_data_for_map(
            data_mock,
            'state',
            'children',
            'all',
            20,
            60
        )
        self.assertEquals(average, 0.0)
