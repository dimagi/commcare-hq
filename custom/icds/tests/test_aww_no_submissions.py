from datetime import datetime, timedelta
from django.test import TestCase
import mock

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.locations.tests.util import make_loc, setup_location_types
from corehq.apps.users.models import CommCareUser
from custom.icds.messaging.custom_content import run_indicator_for_user
from custom.icds.messaging.indicators import AWWSubmissionPerformanceIndicator
from custom.icds_reports.models.aggregate import AggregateInactiveAWW


@mock.patch('custom.icds.messaging.indicators.is_aggregate_inactive_aww_data_fresh', return_value=True)
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
        cls.user_sans_aggregation = make_user('user_sans_aggregation', cls.loc)
        cls.agg_inactive_aww = AggregateInactiveAWW.objects.create(
            awc_site_code=cls.user.raw_username,
            awc_id=cls.loc._id,
            last_submission=None,
        )

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()
        super(TestAWWSubmissionPerformanceIndicator, cls).tearDownClass()

    @property
    def now(self):
        return datetime.utcnow()

    def test_form_sent_today(self, patch):
        self.agg_inactive_aww.last_submission = self.now
        self.agg_inactive_aww.save()
        messages = run_indicator_for_user(self.user, AWWSubmissionPerformanceIndicator, language_code='en')
        self.assertEqual(len(messages), 0)

    def test_form_sent_just_under_seven_days_ago(self, patch):
        self.agg_inactive_aww.last_submission = self.now - timedelta(days=6, hours=23)
        self.agg_inactive_aww.save()
        messages = run_indicator_for_user(self.user, AWWSubmissionPerformanceIndicator, language_code='en')
        self.assertEqual(len(messages), 0)

    def test_form_sent_eight_days_ago(self, patch):
        self.agg_inactive_aww.last_submission = self.now - timedelta(days=8)
        self.agg_inactive_aww.save()
        messages = run_indicator_for_user(self.user, AWWSubmissionPerformanceIndicator, language_code='en')
        self.assertEqual(len(messages), 1)
        self.assertIn('one week', messages[0])

    def test_form_sent_thirty_days_ago(self, patch):
        self.agg_inactive_aww.last_submission = self.now - timedelta(days=29, hours=23)
        self.agg_inactive_aww.save()
        messages = run_indicator_for_user(self.user, AWWSubmissionPerformanceIndicator, language_code='en')
        self.assertEqual(len(messages), 1)
        self.assertIn('one week', messages[0])

    def test_form_sent_thirty_one_days_ago(self, patch):
        self.agg_inactive_aww.last_submission = self.now - timedelta(days=31)
        self.agg_inactive_aww.save()
        messages = run_indicator_for_user(self.user, AWWSubmissionPerformanceIndicator, language_code='en')
        self.assertEqual(len(messages), 1)
        self.assertIn('one month', messages[0])

    def test_no_last_form_submission(self, patch):
        self.agg_inactive_aww.last_submission = None
        self.agg_inactive_aww.save()
        messages = run_indicator_for_user(self.user, AWWSubmissionPerformanceIndicator, language_code='en')
        self.assertEqual(len(messages), 1)
        self.assertIn('one month', messages[0])

    def test_no_agg_rows(self, patch):
        messages = run_indicator_for_user(
            self.user_sans_aggregation,
            AWWSubmissionPerformanceIndicator,
            language_code='en',
        )
        self.assertEqual(len(messages), 1)
        self.assertIn('one month', messages[0])
