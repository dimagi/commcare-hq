from datetime import datetime, timedelta
from django.test import TestCase
from mock import patch
import pytz

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.locations.tests.util import (
    LocationStructure,
    LocationTypeStructure,
    setup_location_types_with_structure,
    setup_locations_with_structure,
)
from corehq.apps.users.models import CommCareUser
from custom.icds.messaging.custom_content import run_indicator_for_user
from custom.icds.messaging.indicators import LSSubmissionPerformanceIndicator


@patch('custom.icds.messaging.indicators._get_last_submission_dates')
class TestLSSubmissionPerformanceIndicator(TestCase):
    domain = 'domain'

    @classmethod
    def setUpClass(cls):
        super(TestLSSubmissionPerformanceIndicator, cls).setUpClass()
        cls.domain_obj = create_domain(cls.domain)

        location_type_structure = [
            LocationTypeStructure('supervisor', [
                LocationTypeStructure('awc', [])
            ])
        ]
        location_structure = [
            LocationStructure('LSL', 'supervisor', [
                LocationStructure('AWC1', 'awc', []),
                LocationStructure('AWC2', 'awc', []),
            ])
        ]
        cls.loc_types = setup_location_types_with_structure(cls.domain, location_type_structure)
        cls.locs = setup_locations_with_structure(cls.domain, location_structure)
        cls.ls = cls._make_user('ls', cls.locs['LSL'])
        cls.awc1 = cls.locs['AWC1']
        cls.awc2 = cls.locs['AWC2']

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()
        super(TestLSSubmissionPerformanceIndicator, cls).tearDownClass()

    @classmethod
    def _make_user(cls, name, location):
        user = CommCareUser.create(cls.domain, name, 'password', None, None)
        user.set_location(location)
        return user

    @property
    def today(self):
        tz = pytz.timezone('Asia/Kolkata')
        return datetime.now(tz=tz).date()

    def test_form_sent_today(self, last_sub_time):
        last_sub_time.return_value = {
            self.awc1.location_id: self.today,
            self.awc2.location_id: self.today,
        }
        messages = run_indicator_for_user(self.ls, LSSubmissionPerformanceIndicator, language_code='en')
        self.assertEqual(len(messages), 0)

    def test_form_sent_seven_days_ago(self, last_sub_time):
        last_sub_time.return_value = {
            self.awc1.location_id: self.today - timedelta(days=7),
            self.awc2.location_id: self.today - timedelta(days=7)
        }
        messages = run_indicator_for_user(self.ls, LSSubmissionPerformanceIndicator, language_code='en')
        self.assertEqual(len(messages), 0)

    def test_form_sent_eight_days_ago(self, last_sub_time):
        last_sub_time.return_value = {
            self.awc1.location_id: self.today - timedelta(days=8),
            self.awc2.location_id: self.today - timedelta(days=7)
        }
        messages = run_indicator_for_user(self.ls, LSSubmissionPerformanceIndicator, language_code='en')
        self.assertEqual(len(messages), 1)
        message = messages[0]
        self.assertTrue('one week' in message)
        self.assertTrue('AWC1' in message)

    def test_form_sent_thirty_days_ago(self, last_sub_time):
        last_sub_time.return_value = {
            self.awc1.location_id: self.today - timedelta(days=30),
            self.awc2.location_id: self.today - timedelta(days=7)
        }
        messages = run_indicator_for_user(self.ls, LSSubmissionPerformanceIndicator, language_code='en')
        self.assertEqual(len(messages), 1)
        message = messages[0]
        self.assertTrue('one week' in message)
        self.assertTrue('AWC1' in message)

    def test_form_sent_thirty_one_days_ago(self, last_sub_time):
        # last submissions only looks 30 days into past
        last_sub_time.return_value = {
            self.awc2.location_id: self.today - timedelta(days=7)
        }
        messages = run_indicator_for_user(self.ls, LSSubmissionPerformanceIndicator, language_code='en')
        self.assertEqual(len(messages), 1)
        message = messages[0]
        self.assertTrue('one month' in message)
        self.assertTrue('AWC1' in message)

    def test_multiple_awc_eight_days_ago(self, last_sub_time):
        last_sub_time.return_value = {
            self.awc1.location_id: self.today - timedelta(days=8),
            self.awc2.location_id: self.today - timedelta(days=8)
        }
        messages = run_indicator_for_user(self.ls, LSSubmissionPerformanceIndicator, language_code='en')
        self.assertEqual(len(messages), 1)
        message = messages[0]
        self.assertTrue('one week' in message)
        self.assertTrue('AWC1' in message)
        self.assertTrue('AWC2' in message)
