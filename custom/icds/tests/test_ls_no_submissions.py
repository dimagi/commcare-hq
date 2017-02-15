from datetime import date, datetime, timedelta
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
            LocationTypeStructure('lsl', [
                LocationTypeStructure('awc', [])
            ])
        ]
        location_structure = [
            LocationStructure('LSL', 'lsl', [
                LocationStructure('AWC', 'awc', []),
                LocationStructure('AWC2', 'awc', []),
            ])
        ]
        cls.loc_types = setup_location_types_with_structure(cls.domain, location_type_structure)
        for l in cls.loc_types.values():
            l.save()
        cls.locs = setup_locations_with_structure(cls.domain, location_structure)
        for l in cls.locs.values():
            l.save()
        cls.ls = cls._make_user('ls', cls.locs['LSL'])
        cls.aww = cls._make_user('aww', cls.locs['AWC'])

    @classmethod
    def tearDownClass(cls):
        UserESFake.reset_docs()
        cls.aww.delete()
        cls.ls.delete()
        for l in cls.locs.values():
            l.delete()
        for l in cls.loc_types.values():
            l.delete()
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
        self.assertFalse(indicator.should_send())
        self.assertEqual(indicator.get_messages(), [u'', u''])

    def test_form_sent_seven_days_ago(self, last_sub_time):
        last_sub_time.return_value = {self.aww.get_id: self.today - timedelta(days=7)}
        indicator = LSSubmissionPerformanceIndicator(self.domain, self.ls)
        self.assertFalse(indicator.should_send())
        self.assertEqual(indicator.get_messages(), [u'', u''])

    def test_form_sent_eight_days_ago(self, last_sub_time):
        last_sub_time.return_value = {self.aww.get_id: self.today - timedelta(days=8)}
        indicator = LSSubmissionPerformanceIndicator(self.domain, self.ls)
        self.assertTrue(indicator.should_send())
        messages = indicator.get_messages()
        self.assertTrue('one week' in messages[0])
        self.assertTrue('AWC' in messages[0])
        self.assertEqual(messages[1], u'')

    def test_form_sent_thirty_one_days_ago(self, last_sub_time):
        # last submissions only looks 30 days into past
        last_sub_time.return_value = {self.aww.get_id: None}
        indicator = LSSubmissionPerformanceIndicator(self.domain, self.ls)
        self.assertTrue(indicator.should_send())
        messages = indicator.get_messages()
        self.assertEqual(messages[0], u'')
        self.assertTrue('one month' in messages[1])
        self.assertTrue('AWC' in messages[1])

    def test_nothing_from_last_sub(self, last_sub_time):
        # last submissions only looks 30 days into past
        last_sub_time.return_value = {}
        indicator = LSSubmissionPerformanceIndicator(self.domain, self.ls)
        self.assertTrue(indicator.should_send())
        messages = indicator.get_messages()
        self.assertEqual(messages[0], u'')
        self.assertTrue('one month' in messages[1])
        self.assertTrue('AWC' in messages[1])

    def test_multiple_awc_eight_days_ago(self, last_sub_time):
        aww_2 = self._make_user('aww_2', self.locs['AWC2'])
        self.addCleanup(aww_2.delete)
        last_sub_time.return_value = {
            self.aww.get_id: self.today - timedelta(days=8),
            aww_2.get_id: self.today - timedelta(days=8)
        }
        indicator = LSSubmissionPerformanceIndicator(self.domain, self.ls)
        self.assertTrue(indicator.should_send())
        messages = indicator.get_messages()
        self.assertTrue('one week' in messages[0])
        self.assertTrue('AWC, ' in messages[0])
        self.assertTrue('AWC2' in messages[0])
        self.assertEqual(messages[1], u'')
