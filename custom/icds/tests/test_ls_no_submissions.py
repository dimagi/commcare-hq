from __future__ import absolute_import
from datetime import datetime, timedelta
from django.test import TestCase
from mock import patch
import pytz

from corehq.apps.es.fake.users_fake import UserESFake
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.locations.tests.util import (
    LocationStructure,
    LocationTypeStructure,
    setup_location_types_with_structure,
    setup_locations_with_structure,
)
from corehq.apps.users.models import CommCareUser
from custom.icds.messaging.indicators import LSSubmissionPerformanceIndicator


@patch('corehq.apps.locations.dbaccessors.UserES', UserESFake)
@patch('custom.icds.messaging.indicators.get_last_submission_time_for_users')
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
        cls.aww = cls._make_user('aww', cls.locs['AWC1'])

    @classmethod
    def tearDownClass(cls):
        UserESFake.reset_docs()
        cls.domain_obj.delete()
        super(TestLSSubmissionPerformanceIndicator, cls).tearDownClass()

    @classmethod
    def _make_user(cls, name, location):
        user = CommCareUser.create(cls.domain, name, 'password')
        user.set_location(location)
        UserESFake.save_doc(user._doc)
        return user

    @property
    def today(self):
        tz = pytz.timezone('Asia/Kolkata')
        return datetime.now(tz=tz).date()

    def test_form_sent_today(self, last_sub_time):
        last_sub_time.return_value = {self.aww.get_id: self.today}
        indicator = LSSubmissionPerformanceIndicator(self.domain, self.ls)
        self.assertEqual(len(indicator.get_messages(language_code='en')), 0)

    def test_form_sent_seven_days_ago(self, last_sub_time):
        last_sub_time.return_value = {self.aww.get_id: self.today - timedelta(days=7)}
        indicator = LSSubmissionPerformanceIndicator(self.domain, self.ls)
        self.assertEqual(len(indicator.get_messages(language_code='en')), 0)

    def test_form_sent_eight_days_ago(self, last_sub_time):
        last_sub_time.return_value = {self.aww.get_id: self.today - timedelta(days=8)}
        indicator = LSSubmissionPerformanceIndicator(self.domain, self.ls)
        messages = indicator.get_messages(language_code='en')
        self.assertEqual(len(messages), 1)
        message = messages[0]
        self.assertTrue('one week' in message)
        self.assertTrue('AWC1' in message)

    def test_form_sent_thirty_days_ago(self, last_sub_time):
        last_sub_time.return_value = {self.aww.get_id: self.today - timedelta(days=30)}
        indicator = LSSubmissionPerformanceIndicator(self.domain, self.ls)
        messages = indicator.get_messages(language_code='en')
        self.assertEqual(len(messages), 1)
        message = messages[0]
        self.assertTrue('one week' in message)
        self.assertTrue('AWC1' in message)

    def test_form_sent_thirty_one_days_ago(self, last_sub_time):
        # last submissions only looks 30 days into past
        last_sub_time.return_value = {}
        indicator = LSSubmissionPerformanceIndicator(self.domain, self.ls)
        messages = indicator.get_messages(language_code='en')
        self.assertEqual(len(messages), 1)
        message = messages[0]
        self.assertTrue('one month' in message)
        self.assertTrue('AWC1' in message)

    def test_multiple_awc_eight_days_ago(self, last_sub_time):
        aww_2 = self._make_user('aww_2', self.locs['AWC2'])
        self.addCleanup(aww_2.delete)
        last_sub_time.return_value = {
            self.aww.get_id: self.today - timedelta(days=8),
            aww_2.get_id: self.today - timedelta(days=8)
        }
        indicator = LSSubmissionPerformanceIndicator(self.domain, self.ls)
        messages = indicator.get_messages(language_code='en')
        self.assertEqual(len(messages), 1)
        message = messages[0]
        self.assertTrue('one week' in message)
        self.assertTrue('AWC1' in message)
        self.assertTrue('AWC2' in message)
