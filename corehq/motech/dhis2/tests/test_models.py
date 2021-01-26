from datetime import date

from django.core.management import call_command
from django.test import TestCase

from nose.tools import assert_equal

from corehq.motech.models import ConnectionSettings

from ..const import (
    SEND_FREQUENCY_MONTHLY,
    SEND_FREQUENCY_QUARTERLY,
    SEND_FREQUENCY_WEEKLY,
)
from ..models import (
    DataSetMap,
    get_date_range,
    SQLDataSetMap,
    get_info_for_columns,
    get_period,
    get_previous_month,
    get_previous_quarter,
    get_previous_week,
    get_quarter_start_month,
    should_send_on_date,
)


def test_should_send_on_date():
    kwargs_day_result = [
        (
            {'frequency': SEND_FREQUENCY_WEEKLY, 'day_to_send': 5},
            date(2020, 9, 4),
            True,  # Friday Sep 4, 2020 is the 5th day of the week
        ),
        (
            {'frequency': SEND_FREQUENCY_WEEKLY, 'day_to_send': 5},
            date(2020, 9, 5),
            False,  # Saturday Sep 5, 2020 is not the 5th day of the week
        ),
        (
            {'frequency': SEND_FREQUENCY_MONTHLY, 'day_to_send': 5},
            date(2020, 9, 5),
            True,  # Sep 5 is the 5th day of the month
        ),
        (
            {'frequency': SEND_FREQUENCY_MONTHLY, 'day_to_send': 5},
            date(2020, 9, 4),
            False,  # Sep 4 is not the 5th day of the month
        ),
        (
            {'frequency': SEND_FREQUENCY_QUARTERLY, 'day_to_send': 5},
            date(2020, 7, 5),
            True,  # Jul 5 is the 5th day of the quarter
        ),
        (
            {'frequency': SEND_FREQUENCY_QUARTERLY, 'day_to_send': 5},
            date(2020, 9, 5),
            False,  # Sep 5 is not the 5th day of the quarter
        ),
    ]
    for kwargs, day, expected_result in kwargs_day_result:
        dataset_map = DataSetMap(**kwargs)
        result = should_send_on_date(dataset_map, day)
        assert_equal(result, expected_result)


def test_get_previous_week():
    day_start_end = [
        (date(2020, 9, 4), date(2020, 8, 24), date(2020, 8, 30)),  # Friday
        (date(2020, 9, 5), date(2020, 8, 24), date(2020, 8, 30)),  # Saturday
        (date(2020, 9, 6), date(2020, 8, 24), date(2020, 8, 30)),  # Sunday
        (date(2020, 9, 7), date(2020, 8, 31), date(2020, 9, 6)),  # Monday
    ]
    for day, expected_start, expected_end in day_start_end:
        date_span = get_previous_week(day)
        assert_equal(date_span.startdate, expected_start)
        assert_equal(date_span.enddate, expected_end)


def test_get_previous_month():
    day_start_end = [
        (date(2020, 1, 1), date(2019, 12, 1), date(2019, 12, 31)),
        (date(2020, 12, 31), date(2020, 11, 1), date(2020, 11, 30)),
        (date(2020, 7, 15), date(2020, 6, 1), date(2020, 6, 30)),
    ]
    for day, expected_start, expected_end in day_start_end:
        date_span = get_previous_month(day)
        assert_equal(date_span.startdate, expected_start)
        assert_equal(date_span.enddate, expected_end)


def test_get_previous_quarter():
    day_start_end = [
        (date(2020, 1, 1), date(2019, 10, 1), date(2019, 12, 31)),
        (date(2020, 3, 31), date(2019, 10, 1), date(2019, 12, 31)),
        (date(2020, 10, 1), date(2020, 7, 1), date(2020, 9, 30)),
        (date(2020, 12, 31), date(2020, 7, 1), date(2020, 9, 30)),
        (date(2020, 7, 15), date(2020, 4, 1), date(2020, 6, 30)),
    ]
    for day, expected_start, expected_end in day_start_end:
        date_span = get_previous_quarter(day)
        assert_equal(date_span.startdate, expected_start)
        assert_equal(date_span.enddate, expected_end)


def test_get_quarter_start_month():
    months = range(1, 13)
    start_months = (1, 1, 1, 4, 4, 4, 7, 7, 7, 10, 10, 10)
    for month, expected_month in zip(months, start_months):
        start_month = get_quarter_start_month(month)
        assert_equal(start_month, expected_month)


def test_get_period():
    freq_date_period = [
        (SEND_FREQUENCY_WEEKLY, date(2020, 1, 1), '2020W1'),  # Mon
        (SEND_FREQUENCY_WEEKLY, date(2020, 12, 31), '2020W53'),  # NYE
        (SEND_FREQUENCY_MONTHLY, date(2020, 1, 1), '202001'),  # Jan
        (SEND_FREQUENCY_QUARTERLY, date(2020, 1, 1), '2020Q1'),  # Jan
        (SEND_FREQUENCY_QUARTERLY, date(2020, 10, 1), '2020Q4'),  # Oct
    ]
    for frequency, startdate, expected_period in freq_date_period:
        period = get_period(frequency, startdate)
        assert_equal(period, expected_period)


def test_get_date_range():
    freq_date_startdate = [
        (SEND_FREQUENCY_WEEKLY, date(2021, 1, 1), date(2020, 12, 21)),
        (SEND_FREQUENCY_WEEKLY, date(2020, 12, 31), date(2020, 12, 21)),
        (SEND_FREQUENCY_QUARTERLY, date(2020, 1, 31), date(2019, 10, 1)),
        (SEND_FREQUENCY_QUARTERLY, date(2020, 3, 31), date(2019, 10, 1)),
        (SEND_FREQUENCY_QUARTERLY, date(2020, 10, 1), date(2020, 7, 1)),
    ]
    for frequency, send_date, expected_startdate in freq_date_startdate:
        date_range = get_date_range(frequency, send_date)
        assert_equal(date_range.startdate, expected_startdate)


class GetInfoForColumnsTests(TestCase):
    domain = 'test-domain'
    expected_value = {
        'foo_bar': {
            'category_option_combo_id': 'bar456789ab',
            'column': 'foo_bar',
            'comment': None,
            'data_element_id': 'foo456789ab',
            'doc_type': 'DataValueMap',
            'is_org_unit': False,
            'is_period': False,
        },
        'foo_baz': {
            'category_option_combo_id': 'baz456789ab',
            'column': 'foo_baz',
            'comment': None,
            'data_element_id': 'foo456789ab',
            'doc_type': 'DataValueMap',
            'is_org_unit': False,
            'is_period': False,
        },
        'foo_qux': {
            'category_option_combo_id': 'qux456789ab',
            'column': 'foo_qux',
            'comment': None,
            'data_element_id': 'foo456789ab',
            'doc_type': 'DataValueMap',
            'is_org_unit': False,
            'is_period': False,
        },
        'org_unit_id': {
            'is_org_unit': True,
            'is_period': False,
        }
    }

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.connection_settings = ConnectionSettings.objects.create(
            domain=cls.domain,
            name='test connection',
            url='https://dhis2.example.com/'
        )
        cls.dataset_map = DataSetMap.wrap({
            'domain': cls.domain,
            'connection_settings_id': cls.connection_settings.id,
            'ucr_id': 'c0ffee',
            'description': 'test dataset map',
            'frequency': SEND_FREQUENCY_MONTHLY,
            'day_to_send': 5,
            'org_unit_column': 'org_unit_id',
            'datavalue_maps': [{
                'column': 'foo_bar',
                'data_element_id': 'foo456789ab',
                'category_option_combo_id': 'bar456789ab',
            }, {
                'column': 'foo_baz',
                'data_element_id': 'foo456789ab',
                'category_option_combo_id': 'baz456789ab',
            }, {
                'column': 'foo_qux',
                'data_element_id': 'foo456789ab',
                'category_option_combo_id': 'qux456789ab',
            }]
        })
        cls.dataset_map.save()
        call_command('populate_sqldatasetmap')
        cls.sqldataset_map = SQLDataSetMap.objects.get(
            domain=cls.domain,
            couch_id=cls.dataset_map._id,
        )

    @classmethod
    def tearDownClass(cls):
        cls.sqldataset_map.delete()
        cls.dataset_map.delete()
        cls.connection_settings.delete()
        super().tearDownClass()

    def test_couch(self):
        info_for_columns = get_info_for_columns(self.dataset_map)
        self.assertEqual(info_for_columns, self.expected_value)

    def test_sql(self):
        info_for_columns = get_info_for_columns(self.sqldataset_map)
        self.assertEqual(info_for_columns, self.expected_value)
