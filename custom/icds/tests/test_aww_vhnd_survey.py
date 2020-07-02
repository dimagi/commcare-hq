from datetime import datetime, timedelta
from unittest import skip

from django.test import TestCase

import pytz
from mock import patch

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es.fake.users_fake import UserESFake
from corehq.apps.locations.tests.util import (
    LocationStructure,
    LocationTypeStructure,
    setup_location_types_with_structure,
    setup_locations_with_structure,
)
from corehq.apps.users.models import CommCareUser
from custom.icds.messaging.custom_content import run_indicator_for_user
from custom.icds.messaging.indicators import AWWVHNDSurveyIndicator
from custom.icds.tests.test_ls_vhnd_survey import VHNDIndicatorTestMixin


@patch('corehq.apps.locations.dbaccessors.UserES', UserESFake)
class TestAWWVHNDSurveyIndicator(TestCase, VHNDIndicatorTestMixin):
    domain = 'icds-test'

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
        cls.setup_datasource()

    @classmethod
    def tearDownClass(cls):
        UserESFake.reset_docs()
        cls.domain_obj.delete()
        super(TestAWWVHNDSurveyIndicator, cls).tearDownClass()

    @classmethod
    def _make_user(cls, name, location):
        user = CommCareUser.create(cls.domain, name, 'password', None, None)
        user.set_location(location)
        UserESFake.save_doc(user._doc)
        return user

    @property
    def today(self):
        tz = pytz.timezone('Asia/Kolkata')
        return datetime.now(tz=tz).date()

    def test_survey_date_today(self):
        self._save_form(self.aww.get_id, self.today)
        messages = run_indicator_for_user(self.aww, AWWVHNDSurveyIndicator, language_code='en')
        self.assertEqual(len(messages), 0)

    def test_form_sent_thirty_six_days_ago(self):
        self._save_form(self.aww.get_id, self.today - timedelta(days=36))
        messages = run_indicator_for_user(self.aww, AWWVHNDSurveyIndicator, language_code='en')
        self.assertEqual(len(messages), 0)

    def test_form_sent_thirty_seven_days_ago(self):
        self._save_form(self.aww.get_id, self.today - timedelta(days=37))
        messages = run_indicator_for_user(self.aww, AWWVHNDSurveyIndicator, language_code='en')
        self.assertEqual(len(messages), 1)
        self.assertTrue('VHSND could not happen at your centre' in messages[0])

    def test_no_form_submitted(self):
        messages = run_indicator_for_user(self.aww, AWWVHNDSurveyIndicator, language_code='en')
        self.assertEqual(len(messages), 1)
        self.assertTrue('VHSND could not happen at your centre' in messages[0])
