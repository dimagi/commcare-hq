from django.test import SimpleTestCase

from custom.icds_reports.utils import generate_data_for_map


class TestUtils(SimpleTestCase):

    def test_calculate_average(self):
        data_mock = [{'all': 9, 'children': 9, 'state_name': 'State 1', 'state_map_location_name': 'test1'},
                    {'all': 0, 'children': 0, 'state_name': 'State 2', 'state_map_location_name': 'test2'},
                    {'all': 0, 'children': 0, 'state_name': 'State 3', 'state_map_location_name': 'test3'},
                    {'all': 0, 'children': 0, 'state_name': 'State 4', 'state_map_location_name': 'test4'},
                    {'all': 6, 'children': 0, 'state_name': 'State 5', 'state_map_location_name': 'test5'}]
        data_for_map, valid_total, in_month_total, average, total = generate_data_for_map(
            data_mock,
            'state',
            'children',
            'all',
            20,
            60
        )
        self.assertEqual(average, 60.0)

    def test_calculate_average_if_one_location(self):
        data_mock = [{'all': 9, 'children': 9, 'state_name': 'State 1', 'state_map_location_name': 'test1'}]
        data_for_map, valid_total, in_month_total, average, total = generate_data_for_map(
            data_mock,
            'state',
            'children',
            'all',
            20,
            60
        )
        self.assertEqual(average, 100.0)

    def test_calculate_average_if_divide_by_zero(self):
        data_mock = [{'all': 0, 'children': 0, 'state_name': 'State 1', 'state_map_location_name': 'test1'}]
        data_for_map, valid_total, in_month_total, average, total = generate_data_for_map(
            data_mock,
            'state',
            'children',
            'all',
            20,
            60
        )
        self.assertEqual(average, 0.0)

    def test_calculate_average_if_data_are_none(self):
        data_mock = [{'all': None, 'children': None, 'state_name': None, 'state_map_location_name': None}]
        data_for_map, valid_total, in_month_total, average, total = generate_data_for_map(
            data_mock,
            'state',
            'children',
            'all',
            20,
            60
        )
        self.assertEqual(average, 0.0)
