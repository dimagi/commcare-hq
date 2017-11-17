from __future__ import absolute_import
from datetime import datetime, timedelta
from django.test import TestCase
from mock import patch
import pytz

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.locations.tests.util import make_loc, setup_location_types
from corehq.apps.users.models import CommCareUser
from custom.icds.messaging.indicators import AWWSubmissionPerformanceIndicator


@patch('custom.icds.messaging.indicators.get_last_submission_time_for_users')
class TestAWWSubmissionPerformanceIndicator(TestCase):
    domain = 'domain'

    @classmethod
    def setUpClass(cls):
        super(TestAWWSubmissionPerformanceIndicator, cls).setUpClass()
        cls.domain_obj = create_domain(cls.domain)

        def make_user(name, location):
            user = CommCareUser.create(cls.domain, name, 'password')
            user.set_location(location)
            return user

        cls.loc_types = setup_location_types(cls.domain, ['awc'])
        cls.loc = make_loc('awc', type='awc', domain=cls.domain)
        cls.user = make_user('user', cls.loc)

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()
        super(TestAWWSubmissionPerformanceIndicator, cls).tearDownClass()

    @property
    def today(self):
        tz = pytz.timezone('Asia/Kolkata')
        return datetime.now(tz=tz).date()

    def test_form_sent_today(self, aww_user_ids):
        aww_user_ids.return_value = {self.user.get_id: self.today}
        indicator = AWWSubmissionPerformanceIndicator(self.domain, self.user)
        messages = indicator.get_messages(language_code='en')
        self.assertEqual(len(messages), 0)

    def test_form_sent_seven_days_ago(self, aww_user_ids):
        aww_user_ids.return_value = {self.user.get_id: self.today - timedelta(days=7)}
        indicator = AWWSubmissionPerformanceIndicator(self.domain, self.user)
        messages = indicator.get_messages(language_code='en')
        self.assertEqual(len(messages), 0)

    def test_form_sent_eight_days_ago(self, aww_user_ids):
        aww_user_ids.return_value = {self.user.get_id: self.today - timedelta(days=8)}
        indicator = AWWSubmissionPerformanceIndicator(self.domain, self.user)
        messages = indicator.get_messages(language_code='en')
        self.assertEqual(len(messages), 1)
        self.assertTrue('one week' in messages[0])

    def test_form_sent_thirty_days_ago(self, aww_user_ids):
        aww_user_ids.return_value = {self.user.get_id: self.today - timedelta(days=30)}
        indicator = AWWSubmissionPerformanceIndicator(self.domain, self.user)
        messages = indicator.get_messages(language_code='en')
        self.assertEqual(len(messages), 1)
        self.assertTrue('one week' in messages[0])

    def test_form_sent_thirty_one_days_ago(self, aww_user_ids):
        # last submissions only looks 30 days into past
        aww_user_ids.return_value = {}
        indicator = AWWSubmissionPerformanceIndicator(self.domain, self.user)
        messages = indicator.get_messages(language_code='en')
        self.assertEqual(len(messages), 1)
        self.assertTrue('one month' in messages[0])
