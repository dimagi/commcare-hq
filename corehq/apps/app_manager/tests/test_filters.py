from __future__ import absolute_import
from __future__ import unicode_literals
import datetime
from collections import namedtuple
from contextlib import contextmanager
from django.test import SimpleTestCase, TestCase
from mock import Mock, patch
from corehq.apps.app_manager.models import (
    AncestorLocationTypeFilter,
    CustomMonthFilter,
    NumericFilter,
    _filter_by_case_sharing_group_id,
    _filter_by_location_id,
    _filter_by_parent_location_id,
    _filter_by_username,
    _filter_by_user_id,
)
from corehq.apps.domain.models import Domain
from corehq.apps.locations.models import SQLLocation, LocationType
from corehq.apps.reports_core.filters import Choice, DynamicChoiceListFilter
from corehq.apps.userreports.reports.filters.choice_providers import DataSourceColumnChoiceProvider
from corehq.apps.userreports.reports.filters.values import dynamic_choice_list_url
from corehq.apps.users.models import CommCareUser


Date = namedtuple('Date', ('year', 'month', 'day'))


DOMAIN = 'test_domain'
MAY_15 = Date(2015, 5, 15)
MAY_20 = Date(2015, 5, 20)
MAY_21 = Date(2015, 5, 21)


@contextmanager
def patch_today(year, month, day):
    date_class = datetime.date
    with patch('datetime.date') as date_patch:
        date_patch.today.return_value = date_class(year, month, day)
        date_patch.side_effect = lambda *args, **kwargs: date_class(*args, **kwargs)
        yield date_patch


class CustomMonthFilterTests(SimpleTestCase):

    def setUp(self):
        self.date_class = datetime.date

    # Assume it was May 15:
    # Period 0, day 21, you would sync April 21-May 20th
    # Period 1, day 21, you would sync March 21-April 20th
    # Period 2, day 21, you would sync February 21-March 20th

    def test_may15_period0(self):
        with patch_today(*MAY_15):
            filter_ = CustomMonthFilter(start_of_month=21, period=0)
            date_span = filter_.get_filter_value(user=None, ui_filter=None)
            self.assertEqual(date_span.startdate, self.date_class(year=2015, month=4, day=21))
            self.assertEqual(date_span.enddate, self.date_class(year=2015, month=5, day=20))

    def test_may15_period1(self):
        with patch_today(*MAY_15):
            filter_ = CustomMonthFilter(start_of_month=21, period=1)
            date_span = filter_.get_filter_value(user=None, ui_filter=None)
            self.assertEqual(date_span.startdate, self.date_class(year=2015, month=3, day=21))
            self.assertEqual(date_span.enddate, self.date_class(year=2015, month=4, day=20))

    def test_may15_period2(self):
        with patch_today(*MAY_15):
            filter_ = CustomMonthFilter(start_of_month=21, period=2)
            date_span = filter_.get_filter_value(user=None, ui_filter=None)
            self.assertEqual(date_span.startdate, self.date_class(year=2015, month=2, day=21))
            self.assertEqual(date_span.enddate, self.date_class(year=2015, month=3, day=20))

    # Assume it was May 20:
    # Period 0, day 21, you would sync April 21-May 20th
    # Period 1, day 21, you would sync March 21-April 20th
    # Period 2, day 21, you would sync February 21-March 20th

    def test_may20_period0(self):
        with patch_today(*MAY_20):
            filter_ = CustomMonthFilter(start_of_month=21, period=0)
            date_span = filter_.get_filter_value(user=None, ui_filter=None)
            self.assertEqual(date_span.startdate, self.date_class(year=2015, month=4, day=21))
            self.assertEqual(date_span.enddate, self.date_class(*MAY_20))

    def test_may20_period1(self):
        with patch_today(*MAY_20):
            filter_ = CustomMonthFilter(start_of_month=21, period=1)
            date_span = filter_.get_filter_value(user=None, ui_filter=None)
            self.assertEqual(date_span.startdate, self.date_class(year=2015, month=3, day=21))
            self.assertEqual(date_span.enddate, self.date_class(year=2015, month=4, day=20))

    def test_may20_period2(self):
        with patch_today(*MAY_20):
            filter_ = CustomMonthFilter(start_of_month=21, period=2)
            date_span = filter_.get_filter_value(user=None, ui_filter=None)
            self.assertEqual(date_span.startdate, self.date_class(year=2015, month=2, day=21))
            self.assertEqual(date_span.enddate, self.date_class(year=2015, month=3, day=20))

    # Assume it was May 21:
    # Period 0, day 21, you would sync May 21-June 20th
    # Period 1, day 21, you would sync April 21-May 20th
    # Period 2, day 21, you would sync March 21-April 20th

    def test_may21_period0(self):
        with patch_today(*MAY_21):
            filter_ = CustomMonthFilter(start_of_month=21, period=0)
            date_span = filter_.get_filter_value(user=None, ui_filter=None)
            self.assertEqual(date_span.startdate, self.date_class(*MAY_21))
            self.assertEqual(date_span.enddate, self.date_class(year=2015, month=6, day=20))

    def test_may21_period1(self):
        with patch_today(*MAY_21):
            filter_ = CustomMonthFilter(start_of_month=21, period=1)
            date_span = filter_.get_filter_value(user=None, ui_filter=None)
            self.assertEqual(date_span.startdate, self.date_class(year=2015, month=4, day=21))
            self.assertEqual(date_span.enddate, self.date_class(*MAY_20))

    def test_may21_period2(self):
        with patch_today(*MAY_21):
            filter_ = CustomMonthFilter(start_of_month=21, period=2)
            date_span = filter_.get_filter_value(user=None, ui_filter=None)
            self.assertEqual(date_span.startdate, self.date_class(year=2015, month=3, day=21))
            self.assertEqual(date_span.enddate, self.date_class(year=2015, month=4, day=20))

    # May 15 for 10 days from the end of the month (start_of_month = -10):
    # Period 0, day 21, you would sync April 20-May 20th
    # Period 1, day 21, you would sync March 21-April 19th
    # Period 2, day 21, you would sync February 18-March 20th

    def test_may15_minus10_period0(self):
        with patch_today(*MAY_15):
            filter_ = CustomMonthFilter(start_of_month=-10, period=0)
            date_span = filter_.get_filter_value(user=None, ui_filter=None)
            self.assertEqual(date_span.startdate, self.date_class(year=2015, month=4, day=20))
            self.assertEqual(date_span.enddate, self.date_class(year=2015, month=5, day=20))

    def test_may15_minus10_period1(self):
        with patch_today(*MAY_15):
            filter_ = CustomMonthFilter(start_of_month=-10, period=1)
            date_span = filter_.get_filter_value(user=None, ui_filter=None)
            self.assertEqual(date_span.startdate, self.date_class(year=2015, month=3, day=21))
            self.assertEqual(date_span.enddate, self.date_class(year=2015, month=4, day=19))

    def test_may15_minus10_period2(self):
        with patch_today(*MAY_15):
            filter_ = CustomMonthFilter(start_of_month=-10, period=2)
            date_span = filter_.get_filter_value(user=None, ui_filter=None)
            self.assertEqual(date_span.startdate, self.date_class(year=2015, month=2, day=18))
            self.assertEqual(date_span.enddate, self.date_class(year=2015, month=3, day=20))


class AutoFilterTests(TestCase):

    @classmethod
    def setUpClass(cls):
        super(AutoFilterTests, cls).setUpClass()
        cls.domain = Domain(name=DOMAIN)
        cls.domain.save()

        cls.country = LocationType(domain=DOMAIN, name='country')
        cls.country.save()
        cls.state = LocationType(
            domain=DOMAIN,
            name='state',
            parent_type=cls.country,
        )
        cls.state.save()
        cls.city = LocationType(
            domain=DOMAIN,
            name='city',
            parent_type=cls.state,
            shares_cases=True,
        )
        cls.city.save()

        cls.usa = SQLLocation(
            domain=DOMAIN,
            name='The United States of America',
            site_code='usa',
            location_type=cls.country,
        )
        cls.usa.save()
        cls.massachusetts = SQLLocation(
            domain=DOMAIN,
            name='Massachusetts',
            site_code='massachusetts',
            location_type=cls.state,
            parent=cls.usa,
        )
        cls.massachusetts.save()
        cls.new_york = SQLLocation(
            domain=DOMAIN,
            name='New York',
            site_code='new_york',
            location_type=cls.state,
            parent=cls.usa,
        )
        cls.new_york.save()

        cls.cambridge = SQLLocation(
            domain=DOMAIN,
            name='Cambridge',
            site_code='cambridge',
            location_type=cls.city,
            parent=cls.massachusetts,
        )
        cls.cambridge.save()
        cls.somerville = SQLLocation(
            domain=DOMAIN,
            name='Somerville',
            site_code='somerville',
            location_type=cls.city,
            parent=cls.massachusetts,
        )
        cls.somerville.save()
        cls.nyc = SQLLocation(
            domain=DOMAIN,
            name='New York City',
            site_code='nyc',
            location_type=cls.city,
            parent=cls.new_york,
        )
        cls.nyc.save()

        cls.drew = CommCareUser(
            domain=DOMAIN,
            username='drew',
            location_id=cls.nyc.location_id,
            assigned_location_ids=[cls.nyc.location_id],
        )
        cls.jon = CommCareUser(
            domain=DOMAIN,
            username='jon',
            location_id=cls.cambridge.location_id,
            assigned_location_ids=[cls.cambridge.location_id],
        )
        cls.nate = CommCareUser(
            domain=DOMAIN,
            username='nate',
            location_id=cls.somerville.location_id,
            assigned_location_ids=[cls.somerville.location_id],
        )
        cls.sheel = CommCareUser(
            domain=DOMAIN,
            username='sheel',
            location_id=cls.somerville.location_id,
            assigned_location_ids=[cls.somerville.location_id],
            last_login=datetime.datetime.now(),
            date_joined=datetime.datetime.now(),
        )
        cls.sheel.save()

    def setUp(self):
        self.ui_filter = Mock()
        self.ui_filter.name = 'test_filter'
        self.ui_filter.value.return_value = 'result'

    @classmethod
    def tearDownClass(cls):
        cls.sheel.delete()
        cls.nyc.delete()
        cls.somerville.delete()
        cls.cambridge.delete()
        cls.new_york.delete()
        cls.massachusetts.delete()
        cls.usa.delete()
        cls.city.delete()
        cls.state.delete()
        cls.country.delete()
        cls.domain.delete()
        super(AutoFilterTests, cls).tearDownClass()

    def test_filter_by_case_sharing_group_id(self):
        result = _filter_by_case_sharing_group_id(self.sheel, None)
        self.assertEqual(result, [Choice(value=self.somerville.location_id, display=None)])

    def test_filter_by_location_id(self):
        result = _filter_by_location_id(self.drew, self.ui_filter)
        self.ui_filter.value.assert_called_with(test_filter=self.nyc.location_id,
                                                request_user=self.drew)
        self.assertEqual(result, 'result')

    def test_filter_by_parent_location_id(self):
        result = _filter_by_parent_location_id(self.jon, self.ui_filter)
        self.ui_filter.value.assert_called_with(test_filter=self.massachusetts.location_id,
                                                request_user=self.jon)
        self.assertEqual(result, 'result')

    def test_filter_by_username(self):
        result = _filter_by_username(self.sheel, None)
        self.assertEqual(result, Choice(value='sheel', display=None))

    def test_filter_by_user_id(self):
        result = _filter_by_user_id(self.sheel, None)
        self.assertEqual(result, Choice(value=self.sheel._id, display=None))

    def _get_dynamic_choice_list_ui_filter(self):
        return DynamicChoiceListFilter(
            "my name",
            "my_field",
            "string",
            "my label",
            True,
            dynamic_choice_list_url,
            DataSourceColumnChoiceProvider(None, None),
        )

    # AncestorLocationTypeFilter is not an AutoFilter, but we'll hitch a ride here to reuse setup and teardown
    def test_ancestor_location_type_filter(self):
        ucr_filter = AncestorLocationTypeFilter(ancestor_location_type_name='state')
        ui_filter = self._get_dynamic_choice_list_ui_filter()
        ancestor_state_value = ucr_filter.get_filter_value(self.nate, ui_filter)
        self.assertEqual(
            ancestor_state_value,
            [Choice(
                value=self.massachusetts.location_id,
                display=self.massachusetts.location_id
            )]
        )

    def test_ancestor_location_type_filter_with_no_location_found(self):
        ucr_filter = AncestorLocationTypeFilter(ancestor_location_type_name='banana')
        ui_filter = self._get_dynamic_choice_list_ui_filter()
        ancestor_state_value = ucr_filter.get_filter_value(self.nate, ui_filter)
        self.assertEqual(ancestor_state_value, ui_filter.default_value())


class NumericFilterTests(SimpleTestCase):

    def test_numeric_filter(self):
        self.assertEqual(
            NumericFilter.wrap({'operator': '>', 'operand': '1.5'}).get_filter_value(None, None),
            {'operator': '>', 'operand': 1.5}
        )
