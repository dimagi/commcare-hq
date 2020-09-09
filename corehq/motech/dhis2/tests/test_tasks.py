from datetime import date

from django.test import SimpleTestCase, TestCase

import attr

from corehq.motech.dhis2.const import (
    SEND_FREQUENCY_MONTHLY,
    SEND_FREQUENCY_QUARTERLY,
    SEND_FREQUENCY_WEEKLY,
)
from corehq.motech.dhis2.dbaccessors import get_migrated_dataset_maps
from corehq.motech.dhis2.models import DataSetMap
from corehq.motech.dhis2.tasks import (
    get_info_for_columns,
    get_period,
    get_previous_month,
    get_previous_quarter,
    get_previous_week,
    should_send_on_date,
)
from corehq.motech.models import ConnectionSettings


@attr.s(auto_attribs=True, kw_only=True)
class DataSetMapDuck:
    frequency: str
    day_to_send: int


class ShouldSendOnDateTests(SimpleTestCase):
    def test_weekly_yes(self):
        dataset_map = DataSetMapDuck(
            frequency=SEND_FREQUENCY_WEEKLY,
            day_to_send=5,
        )
        friday = date(2020, 9, 4)
        self.assertTrue(should_send_on_date(dataset_map, friday))

    def test_weekly_no(self):
        dataset_map = DataSetMapDuck(
            frequency=SEND_FREQUENCY_WEEKLY,
            day_to_send=5,
        )
        saturday = date(2020, 9, 5)
        self.assertFalse(should_send_on_date(dataset_map, saturday))

    def test_monthly_yes(self):
        dataset_map = DataSetMapDuck(
            frequency=SEND_FREQUENCY_MONTHLY,
            day_to_send=5,
        )
        the_fifth = date(2020, 9, 5)
        self.assertTrue(should_send_on_date(dataset_map, the_fifth))

    def test_monthly_no(self):
        dataset_map = DataSetMapDuck(
            frequency=SEND_FREQUENCY_MONTHLY,
            day_to_send=5,
        )
        the_fourth = date(2020, 9, 4)
        self.assertFalse(should_send_on_date(dataset_map, the_fourth))

    def test_quarterly_yes(self):
        dataset_map = DataSetMapDuck(
            frequency=SEND_FREQUENCY_QUARTERLY,
            day_to_send=5,
        )
        july = date(2020, 7, 5)
        self.assertTrue(should_send_on_date(dataset_map, july))

    def test_quarterly_no(self):
        dataset_map = DataSetMapDuck(
            frequency=SEND_FREQUENCY_QUARTERLY,
            day_to_send=5,
        )
        september = date(2020, 9, 5)
        self.assertFalse(should_send_on_date(dataset_map, september))


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
        cls.connx = ConnectionSettings.objects.create(
            domain=cls.domain,
            name='test connection',
            url='https://dhis2.example.com/'
        )
        cls.dataset_map = DataSetMap.wrap({
            'domain': cls.domain,
            'connection_settings_id': cls.connx.id,
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
        cls.migrated = get_migrated_dataset_maps(cls.domain)

    @classmethod
    def tearDownClass(cls):
        for m in cls.migrated:
            m.delete()
        cls.dataset_map.delete()
        cls.connx.delete()
        super().tearDownClass()

    def test_couch(self):
        info_for_columns = get_info_for_columns(self.dataset_map)
        self.assertEqual(info_for_columns, self.expected_value)

    def test_sql(self):
        info_for_columns = get_info_for_columns(self.migrated[0])
        self.assertEqual(info_for_columns, self.expected_value)


class GetPreviousWeekTests(SimpleTestCase):

    def test_friday(self):
        friday = date(2020, 9, 4)
        date_span = get_previous_week(friday)
        self.assertEqual(date_span.startdate, date(2020, 8, 24))
        self.assertEqual(date_span.enddate, date(2020, 8, 30))

    def test_saturday(self):
        saturday = date(2020, 9, 5)
        date_span = get_previous_week(saturday)
        self.assertEqual(date_span.startdate, date(2020, 8, 24))
        self.assertEqual(date_span.enddate, date(2020, 8, 30))

    def test_sunday(self):
        sunday = date(2020, 9, 6)
        date_span = get_previous_week(sunday)
        self.assertEqual(date_span.startdate, date(2020, 8, 24))
        self.assertEqual(date_span.enddate, date(2020, 8, 30))

    def test_monday(self):
        monday = date(2020, 9, 7)
        date_span = get_previous_week(monday)
        self.assertEqual(date_span.startdate, date(2020, 8, 31))
        self.assertEqual(date_span.enddate, date(2020, 9, 6))


class GetPreviousMonthTests(SimpleTestCase):
    def test_first_month(self):
        date_span = get_previous_month(date(2020, 1, 1))
        self.assertEqual(date_span.startdate, date(2019, 12, 1))
        self.assertEqual(date_span.enddate, date(2019, 12, 31))

    def test_last_month(self):
        date_span = get_previous_month(date(2020, 12, 31))
        self.assertEqual(date_span.startdate, date(2020, 11, 1))
        self.assertEqual(date_span.enddate, date(2020, 11, 30))

    def test_other_month(self):
        date_span = get_previous_month(date(2020, 7, 15))
        self.assertEqual(date_span.startdate, date(2020, 6, 1))
        self.assertEqual(date_span.enddate, date(2020, 6, 30))


class GetPreviousQuarterTests(SimpleTestCase):
    def test_first_month_first_quarter(self):
        date_span = get_previous_quarter(date(2020, 1, 1))
        self.assertEqual(date_span.startdate, date(2019, 10, 1))
        self.assertEqual(date_span.enddate, date(2019, 12, 31))

    def test_last_month_first_quarter(self):
        date_span = get_previous_quarter(date(2020, 3, 31))
        self.assertEqual(date_span.startdate, date(2019, 10, 1))
        self.assertEqual(date_span.enddate, date(2019, 12, 31))

    def test_first_month_last_quarter(self):
        date_span = get_previous_quarter(date(2020, 10, 1))
        self.assertEqual(date_span.startdate, date(2020, 7, 1))
        self.assertEqual(date_span.enddate, date(2020, 9, 30))

    def test_last_month_last_quarter(self):
        date_span = get_previous_quarter(date(2020, 12, 31))
        self.assertEqual(date_span.startdate, date(2020, 7, 1))
        self.assertEqual(date_span.enddate, date(2020, 9, 30))

    def test_other_quarter(self):
        date_span = get_previous_quarter(date(2020, 7, 15))
        self.assertEqual(date_span.startdate, date(2020, 4, 1))
        self.assertEqual(date_span.enddate, date(2020, 6, 30))


class GetPeriodTests(SimpleTestCase):

    def test_first_week_starts_monday(self):
        monday = date(2020, 1, 1)
        period = get_period(SEND_FREQUENCY_WEEKLY, monday)
        self.assertEqual(period, '2020W1')

    def test_first_week_starts_non_monday(self):
        friday = date(2021, 1, 1)
        period = get_period(SEND_FREQUENCY_WEEKLY, friday)
        self.assertEqual(period, '2021W1')

    def test_last_week(self):
        nye = date(2020, 12, 31)
        period = get_period(SEND_FREQUENCY_WEEKLY, nye)
        self.assertEqual(period, '2020W53')

    def test_first_month(self):
        january = date(2020, 1, 1)
        period = get_period(SEND_FREQUENCY_MONTHLY, january)
        self.assertEqual(period, '202001')

    def test_first_quarter(self):
        january = date(2020, 1, 1)
        period = get_period(SEND_FREQUENCY_QUARTERLY, january)
        self.assertEqual(period, '2020Q1')

    def test_first_quarter_enddate(self):
        march = date(2020, 3, 31)
        period = get_period(SEND_FREQUENCY_QUARTERLY, march)
        self.assertEqual(period, '2020Q1')

    def test_last_quarter(self):
        october = date(2020, 10, 1)
        period = get_period(SEND_FREQUENCY_QUARTERLY, october)
        self.assertEqual(period, '2020Q4')
