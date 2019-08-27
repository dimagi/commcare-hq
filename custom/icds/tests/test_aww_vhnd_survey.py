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
from custom.icds.messaging.custom_content import run_indicator_for_user
from custom.icds.messaging.indicators import AWWVHNDSurveyIndicator


@patch('corehq.apps.locations.dbaccessors.UserES', UserESFake)
@patch('custom.icds.messaging.indicators.get_last_form_submissions_by_user')
class TestAWWVHNDSurveyIndicator(TestCase):
    domain = 'domain'

    @classmethod
    def setUpClass(cls):
        super(TestAWWVHNDSurveyIndicator, cls).setUpClass()
        cls.domain_obj = create_domain(cls.domain)

        location_type_structure = [
            LocationTypeStructure('supervisor', [
                LocationTypeStructure('awc', [])
            ])
        ]
        location_structure = [
            LocationStructure('LSL', 'supervisor', [
                LocationStructure('AWC1', 'awc', []),
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
        super(TestAWWVHNDSurveyIndicator, cls).tearDownClass()

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

    def _make_form(self, user_id, date):
        def es_formatted_date(date):
            return date.strftime('%Y-%m-%d')

        return {
            'form': {
                'meta': {
                    'user_id': user_id
                },
                'vhsnd_date_past_month': es_formatted_date(date),
            }
        }

    def test_survey_date_today(self, last_subs):
        last_subs.return_value = {
            self.aww.get_id: [self._make_form(self.aww.get_id, self.today)]
        }
        messages = run_indicator_for_user(self.aww, AWWVHNDSurveyIndicator, language_code='en')
        self.assertEqual(len(messages), 0)

    def test_form_sent_thirty_six_days_ago(self, last_subs):
        last_subs.return_value = {
            self.aww.get_id: [self._make_form(self.aww.get_id, self.today - timedelta(days=36))]
        }
        messages = run_indicator_for_user(self.aww, AWWVHNDSurveyIndicator, language_code='en')
        self.assertEqual(len(messages), 0)

    def test_form_sent_thirty_seven_days_ago(self, last_subs):
        last_subs.return_value = {
            self.aww.get_id: [self._make_form(self.aww.get_id, self.today - timedelta(days=37))]
        }
        messages = run_indicator_for_user(self.aww, AWWVHNDSurveyIndicator, language_code='en')
        self.assertEqual(len(messages), 1)
        self.assertTrue('VHSND could not happen at your centre' in messages[0])

    def test_no_form_submitted(self, last_subs):
        last_subs.return_value = {}
        messages = run_indicator_for_user(self.aww, AWWVHNDSurveyIndicator, language_code='en')
        self.assertEqual(len(messages), 1)
        self.assertTrue('VHSND could not happen at your centre' in messages[0])
