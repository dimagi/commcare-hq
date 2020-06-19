import uuid
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
from corehq.apps.userreports.models import StaticDataSourceConfiguration
from corehq.apps.userreports.util import get_indicator_adapter
from corehq.apps.users.models import CommCareUser
from custom.icds.const import VHND_SURVEY_XMLNS
from custom.icds.messaging.custom_content import run_indicator_for_user
from custom.icds.messaging.indicators import LSVHNDSurveyIndicator


class VHNDIndicatorTestMixin(object):
    @classmethod
    def setup_datasource(cls):
        datasource_id = StaticDataSourceConfiguration.get_doc_id(cls.domain, 'static-vhnd_form')
        data_source = StaticDataSourceConfiguration.by_id(datasource_id)
        cls.adapter = get_indicator_adapter(data_source)
        cls.adapter.rebuild_table()

    def _save_form(self, user_id, date):
        def es_formatted_date(date):
            return date.strftime('%Y-%m-%d')

        doc = {
            'form': {
                'meta': {
                    'userID': user_id
                },
                'vhsnd_date_past_month': es_formatted_date(date),
            },
            '_id': uuid.uuid4().hex,
            'domain': self.domain,
            'xmlns': VHND_SURVEY_XMLNS,
            'doc_type': 'XFormInstance',
        }
        self.adapter.save(doc)
        self.addCleanup(self.adapter.delete, doc)


@patch('corehq.apps.locations.dbaccessors.UserES', UserESFake)
class TestLSVHNDSurveyIndicator(TestCase, VHNDIndicatorTestMixin):
    domain = 'icds-test'

    @classmethod
    def setUpClass(cls):
        super(TestLSVHNDSurveyIndicator, cls).setUpClass()
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
        cls.aww1 = cls._make_user('aww1', cls.locs['AWC1'])
        cls.aww2 = cls._make_user('aww2', cls.locs['AWC2'])
        cls.setup_datasource()

    @classmethod
    def tearDownClass(cls):
        UserESFake.reset_docs()
        cls.domain_obj.delete()
        super(TestLSVHNDSurveyIndicator, cls).tearDownClass()

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
        self._save_form(self.aww1.get_id, self.today)
        self._save_form(self.aww2.get_id, self.today)
        messages = run_indicator_for_user(self.ls, LSVHNDSurveyIndicator, language_code='en')
        self.assertEqual(len(messages), 0)

    def test_form_sent_thirty_six_days_ago(self):
        self._save_form(self.aww1.get_id, self.today - timedelta(days=36))
        self._save_form(self.aww2.get_id, self.today - timedelta(days=36))
        messages = run_indicator_for_user(self.ls, LSVHNDSurveyIndicator, language_code='en')
        self.assertEqual(len(messages), 0)

    def test_form_sent_thirty_seven_days_ago(self):
        self._save_form(self.aww1.get_id, self.today - timedelta(days=37))
        self._save_form(self.aww2.get_id, self.today - timedelta(days=36))
        messages = run_indicator_for_user(self.ls, LSVHNDSurveyIndicator, language_code='en')
        self.assertEqual(len(messages), 1)
        self.assertTrue('AWC1' in messages[0])

    def test_multiple_locations(self):
        self._save_form(self.aww1.get_id, self.today - timedelta(days=37))
        self._save_form(self.aww2.get_id, self.today - timedelta(days=37))

        messages = run_indicator_for_user(self.ls, LSVHNDSurveyIndicator, language_code='en')
        self.assertEqual(len(messages), 1)
        message = messages[0]
        self.assertTrue('AWC1' in message)
        self.assertTrue('AWC2' in message)

    def test_multiple_locations_one_is_old(self):
        self._save_form(self.aww2.get_id, self.today - timedelta(days=37))
        self._save_form(self.aww1.get_id, self.today - timedelta(days=15))

        messages = run_indicator_for_user(self.ls, LSVHNDSurveyIndicator, language_code='en')
        self.assertEqual(len(messages), 1)
        message = messages[0]
        self.assertFalse('AWC1' in message)
        self.assertTrue('AWC2' in message)

    def test_no_form_submitted(self):
        messages = run_indicator_for_user(self.ls, LSVHNDSurveyIndicator, language_code='en')
        self.assertEqual(len(messages), 1)
        self.assertTrue('AWC1' in messages[0])
