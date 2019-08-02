from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import datetime, timedelta
from django.test import TestCase
import mock

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.locations.tests.util import make_loc, setup_location_types
from corehq.apps.users.models import CommCareUser
from corehq.warehouse.models import ApplicationDim, ApplicationStatusFact, Batch, UserDim
from custom.icds.messaging.custom_content import run_indicator_for_user
from custom.icds.messaging.indicators import AWWSubmissionPerformanceIndicator


@mock.patch('custom.icds.messaging.indicators.get_warehouse_latest_modified_date', return_value=datetime.utcnow())
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
        cls.user_sans_app_status = make_user('user_sans_app_status', cls.loc)
        cls.batch = Batch.objects.create(
            start_datetime=datetime.now(),
            end_datetime=datetime.now(),
            completed_on=datetime.now(),
            dag_slug='batch',
        )
        cls.app_dim = ApplicationDim.objects.create(
            batch=cls.batch,
            domain=cls.domain,
            application_id=100007,
            name='icds-cas',
            deleted=False,
        )
        cls.user_dim = UserDim.objects.create(
            batch=cls.batch,
            user_id=cls.user.get_id,
            username=cls.user.username,
            user_type=cls.user._get_user_type(),
            doc_type=cls.user.doc_type,
            date_joined=datetime.utcnow() - timedelta(days=5000),
            deleted=False,
        )
        cls.app_fact = ApplicationStatusFact.objects.create(
            batch=cls.batch,
            app_dim=cls.app_dim,
            user_dim=cls.user_dim,
            domain=cls.domain,
            last_form_submission_date=None,
        )

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()
        super(TestAWWSubmissionPerformanceIndicator, cls).tearDownClass()
        # warehouse entities are cleaned up by db transaction rollback

    @property
    def now(self):
        return datetime.utcnow()

    def test_form_sent_today(self):
        self.app_fact.last_form_submission_date = self.now
        self.app_fact.save()
        messages = run_indicator_for_user(self.user, AWWSubmissionPerformanceIndicator, language_code='en')
        self.assertEqual(len(messages), 0)

    def test_form_sent_just_under_seven_days_ago(self):
        self.app_fact.last_form_submission_date = self.now - timedelta(days=6, hours=23)
        self.app_fact.save()
        messages = run_indicator_for_user(self.user, AWWSubmissionPerformanceIndicator, language_code='en')
        self.assertEqual(len(messages), 0)

    def test_form_sent_eight_days_ago(self):
        self.app_fact.last_form_submission_date = self.now - timedelta(days=8)
        self.app_fact.save()
        messages = run_indicator_for_user(self.user, AWWSubmissionPerformanceIndicator, language_code='en')
        self.assertEqual(len(messages), 1)
        self.assertIn('one week', messages[0])

    def test_form_sent_thirty_days_ago(self):
        self.app_fact.last_form_submission_date = self.now - timedelta(days=29, hours=23)
        self.app_fact.save()
        messages = run_indicator_for_user(self.user, AWWSubmissionPerformanceIndicator, language_code='en')
        self.assertEqual(len(messages), 1)
        self.assertIn('one week', messages[0])

    def test_form_sent_thirty_one_days_ago(self):
        self.app_fact.last_form_submission_date = self.now - timedelta(days=31)
        self.app_fact.save()
        messages = run_indicator_for_user(self.user, AWWSubmissionPerformanceIndicator, language_code='en')
        self.assertEqual(len(messages), 1)
        self.assertIn('one month', messages[0])

    def test_no_last_form_submission(self):
        self.app_fact.last_form_submission_date = None
        self.app_fact.save()
        messages = run_indicator_for_user(self.user, AWWSubmissionPerformanceIndicator, language_code='en')
        self.assertEqual(len(messages), 1)
        self.assertIn('one month', messages[0])

    def test_no_app_status_fact(self):
        messages = run_indicator_for_user(
            self.user_sans_app_status,
            AWWSubmissionPerformanceIndicator,
            language_code='en',
        )
        self.assertEqual(len(messages), 1)
        self.assertIn('one month', messages[0])
