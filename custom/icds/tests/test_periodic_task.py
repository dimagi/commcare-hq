from __future__ import absolute_import
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.locations.tests.util import (
    LocationStructure,
    LocationTypeStructure,
    setup_location_types_with_structure,
    setup_locations_with_structure,
)
from corehq.apps.users.models import CommCareUser
from custom.icds.messaging.indicators import (
    AWWAggregatePerformanceIndicator,
    AWWSubmissionPerformanceIndicator,
    LSAggregatePerformanceIndicator,
    LSSubmissionPerformanceIndicator,
    LSVHNDSurveyIndicator,
)
from custom.icds.const import HINDI, TELUGU, MARATHI, ANDHRA_PRADESH_SITE_CODE, MAHARASHTRA_SITE_CODE
from custom.icds.tasks import run_user_indicators
from datetime import date
from django.test import TestCase, override_settings
from mock import patch, call

TEST_DOMAIN = 'icds-indicator-periodic-task'


@override_settings(ICDS_SMS_INDICATOR_DOMAINS=[TEST_DOMAIN])
@patch('custom.icds.tasks.get_user_ids_under_location')
@patch('custom.icds.tasks.get_current_date')
@patch('custom.icds.tasks.run_indicator.delay')
class TestIndicatorPeriodicTask(TestCase):
    domain = TEST_DOMAIN

    @classmethod
    def setUpClass(cls):
        super(TestIndicatorPeriodicTask, cls).setUpClass()
        cls.domain_obj = create_domain(cls.domain)

        location_type_structure = [
            LocationTypeStructure('supervisor', [
                LocationTypeStructure('awc', [])
            ])
        ]
        location_structure = [
            LocationStructure('LS1', 'supervisor', [
                LocationStructure('AWC1', 'awc', []),
                LocationStructure('AWC2', 'awc', []),
            ]),
            LocationStructure('LS2', 'supervisor', [
                LocationStructure('AWC3', 'awc', []),
                LocationStructure('AWC4', 'awc', []),
            ])
        ]
        cls.loc_types = setup_location_types_with_structure(cls.domain, location_type_structure)
        cls.locs = setup_locations_with_structure(cls.domain, location_structure)
        cls.ls1 = cls._make_user('ls1', cls.locs['LS1'])
        cls.ls2 = cls._make_user('ls2', cls.locs['LS2'])
        cls.aww1 = cls._make_user('aww1', cls.locs['AWC1'])
        cls.aww2 = cls._make_user('aww2', cls.locs['AWC2'])
        cls.aww3 = cls._make_user('aww3', cls.locs['AWC3'])
        cls.aww4 = cls._make_user('aww4', cls.locs['AWC4'])

        cls.ls_user_ids = [cls.ls1.get_id, cls.ls2.get_id]
        cls.aww_user_ids = [cls.aww1.get_id, cls.aww2.get_id, cls.aww3.get_id, cls.aww4.get_id]

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()
        super(TestIndicatorPeriodicTask, cls).tearDownClass()

    @classmethod
    def _make_user(cls, name, location):
        user = CommCareUser.create(cls.domain, name, 'password')
        user.set_location(location)
        return user

    def test_monthly_indicators(self, run_indicator_mock, get_current_date_mock,
            get_user_ids_under_location_mock):

        # First of month, but not Monday. Run only monthly indicators
        get_current_date_mock.return_value = date(2017, 11, 1)
        get_user_ids_under_location_mock.return_value = set([])
        run_user_indicators(phased_rollout=False)

        expected_calls = []

        for user_id in self.aww_user_ids:
            expected_calls.append(call(self.domain, user_id, AWWAggregatePerformanceIndicator, HINDI))

        for user_id in self.ls_user_ids:
            expected_calls.append(call(self.domain, user_id, LSAggregatePerformanceIndicator, HINDI))

        self.assertEqual(run_indicator_mock.call_count, len(expected_calls))
        run_indicator_mock.assert_has_calls(expected_calls, any_order=True)

    def test_weekly_indicators(self, run_indicator_mock, get_current_date_mock,
            get_user_ids_under_location_mock):
        # Monday, but not first of month. Run only weekly indicators
        get_current_date_mock.return_value = date(2017, 11, 6)
        get_user_ids_under_location_mock.return_value = set([])
        run_user_indicators(phased_rollout=False)

        expected_calls = []

        for user_id in self.aww_user_ids:
            expected_calls.append(call(self.domain, user_id, AWWSubmissionPerformanceIndicator, HINDI))

        for user_id in self.ls_user_ids:
            expected_calls.append(call(self.domain, user_id, LSSubmissionPerformanceIndicator, HINDI))
            expected_calls.append(call(self.domain, user_id, LSVHNDSurveyIndicator, HINDI))

        self.assertEqual(run_indicator_mock.call_count, len(expected_calls))
        run_indicator_mock.assert_has_calls(expected_calls, any_order=True)

    def _run_special_language(self, expected_language, run_indicator_mock,
            get_current_date_mock, get_user_ids_under_location_mock):

        def get_user_ids_wrap(domain, site_code):
            if site_code == ANDHRA_PRADESH_SITE_CODE and expected_language == TELUGU:
                return set(self.aww_user_ids + self.ls_user_ids)

            if site_code == MAHARASHTRA_SITE_CODE and expected_language == MARATHI:
                return set(self.aww_user_ids + self.ls_user_ids)

            return set([])

        # The first of the month, and a Monday. All indicators are run
        get_current_date_mock.return_value = date(2017, 5, 1)
        get_user_ids_under_location_mock.side_effect = get_user_ids_wrap
        run_user_indicators(phased_rollout=False)

        expected_calls = []

        for user_id in self.aww_user_ids:
            expected_calls.append(call(self.domain, user_id, AWWAggregatePerformanceIndicator, expected_language))
            expected_calls.append(call(self.domain, user_id, AWWSubmissionPerformanceIndicator, expected_language))

        for user_id in self.ls_user_ids:
            expected_calls.append(call(self.domain, user_id, LSAggregatePerformanceIndicator, expected_language))
            expected_calls.append(call(self.domain, user_id, LSSubmissionPerformanceIndicator, expected_language))
            expected_calls.append(call(self.domain, user_id, LSVHNDSurveyIndicator, expected_language))

        self.assertEqual(run_indicator_mock.call_count, len(expected_calls))
        run_indicator_mock.assert_has_calls(expected_calls, any_order=True)

    def test_telugu(self, run_indicator_mock, get_current_date_mock, get_user_ids_under_location_mock):
        self._run_special_language(TELUGU, run_indicator_mock, get_current_date_mock,
            get_user_ids_under_location_mock)

    def test_marathi(self, run_indicator_mock, get_current_date_mock, get_user_ids_under_location_mock):
        self._run_special_language(MARATHI, run_indicator_mock, get_current_date_mock,
            get_user_ids_under_location_mock)
