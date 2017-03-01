from corehq.apps.es.fake.users_fake import UserESFake
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
from custom.icds.tasks import run_weekly_indicators
from django.test import TestCase, override_settings
from mock import patch, call

TEST_DOMAIN = 'icds-indicator-periodic-task'


@override_settings(ICDS_SMS_INDICATOR_DOMAINS=[TEST_DOMAIN])
@patch('corehq.apps.locations.dbaccessors.UserES', UserESFake)
@patch('custom.icds.tasks.is_first_week_of_month')
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
        UserESFake.reset_docs()
        cls.domain_obj.delete()
        super(TestIndicatorPeriodicTask, cls).tearDownClass()

    @classmethod
    def _make_user(cls, name, location):
        user = CommCareUser.create(cls.domain, name, 'password')
        user.set_location(location)
        UserESFake.save_doc(user._doc)
        return user

    def test_periodic_task_during_first_week_of_month(self, run_indicator_mock, is_first_week_of_month_mock):
        is_first_week_of_month_mock.return_value = True
        run_weekly_indicators()

        expected_calls = []

        for user_id in self.aww_user_ids:
            expected_calls.append(call(self.domain, user_id, AWWAggregatePerformanceIndicator))
            expected_calls.append(call(self.domain, user_id, AWWSubmissionPerformanceIndicator))

        for user_id in self.ls_user_ids:
            expected_calls.append(call(self.domain, user_id, LSAggregatePerformanceIndicator))
            expected_calls.append(call(self.domain, user_id, LSSubmissionPerformanceIndicator))
            expected_calls.append(call(self.domain, user_id, LSVHNDSurveyIndicator))

        self.assertEqual(run_indicator_mock.call_count, len(expected_calls))
        run_indicator_mock.assert_has_calls(expected_calls, any_order=True)

    def test_periodic_task_during_rest_of_month(self, run_indicator_mock, is_first_week_of_month_mock):
        is_first_week_of_month_mock.return_value = False
        run_weekly_indicators()

        expected_calls = []

        for user_id in self.aww_user_ids:
            expected_calls.append(call(self.domain, user_id, AWWSubmissionPerformanceIndicator))

        for user_id in self.ls_user_ids:
            expected_calls.append(call(self.domain, user_id, LSSubmissionPerformanceIndicator))
            expected_calls.append(call(self.domain, user_id, LSVHNDSurveyIndicator))

        self.assertEqual(run_indicator_mock.call_count, len(expected_calls))
        run_indicator_mock.assert_has_calls(expected_calls, any_order=True)
