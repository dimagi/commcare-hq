from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
import uuid
from datetime import datetime, timedelta
from django.test import TestCase
from casexml.apps.case.xml import V2
from casexml.apps.phone.tests.utils import call_fixture_generator
from corehq.apps.calendar_fixture.fixture_provider import calendar_fixture_generator
from corehq.apps.calendar_fixture.models import DEFAULT_DAYS_BEFORE, DEFAULT_DAYS_AFTER, CalendarFixtureSettings
from corehq.apps.users.models import CommCareUser
from corehq.const import ONE_DAY
from corehq.util.test_utils import flag_enabled


class TestFixture(TestCase):

    def test_nothing(self):
        user = CommCareUser(_id=uuid.uuid4().hex, domain='not-enabled')
        self.assertEqual([], call_fixture_generator(calendar_fixture_generator, user))

    @flag_enabled('CUSTOM_CALENDAR_FIXTURE')
    def test_fixture_defaults(self):
        user = CommCareUser(_id=uuid.uuid4().hex, domain='test-calendar-defaults')
        fixture = call_fixture_generator(calendar_fixture_generator, user)[0]
        self.assertEqual(user._id, fixture.attrib['user_id'])
        today = datetime.today()
        self._check_first_date(fixture, today - timedelta(days=DEFAULT_DAYS_BEFORE))
        self._check_last_date(fixture, today + timedelta(days=DEFAULT_DAYS_AFTER))

    @flag_enabled('CUSTOM_CALENDAR_FIXTURE')
    def test_fixture_customization(self):
        user = CommCareUser(_id=uuid.uuid4().hex, domain='test-calendar-settings')
        days_before = 50
        days_after = 10
        calendar_settings = CalendarFixtureSettings.objects.create(
            domain='test-calendar-settings',
            days_before=days_before,
            days_after=days_after,
        )
        fixture = call_fixture_generator(calendar_fixture_generator, user)[0]
        self.assertEqual(user._id, fixture.attrib['user_id'])
        today = datetime.today()
        self._check_first_date(fixture, today - timedelta(days=days_before))
        self._check_last_date(fixture, today + timedelta(days=days_after))
        self.addCleanup(calendar_settings.delete)

    def _check_first_date(self, fixture, expected_date):
        year_element = fixture[0][0]
        self.assertEqual(str(expected_date.year), year_element.attrib['number'])
        month_element = fixture[0][0][0]
        self.assertEqual(str(expected_date.month), month_element.attrib['number'])
        day_element = fixture[0][0][0][0]
        self.assertEqual(str(int(expected_date.strftime('%s')) // (ONE_DAY)), day_element.attrib['date'])

    def _check_last_date(self, fixture, expected_date):
        year_element = fixture[0][-1]
        self.assertEqual(str(expected_date.year), year_element.attrib['number'])
        month_element = fixture[0][-1][-1]
        self.assertEqual(str(expected_date.month), month_element.attrib['number'])
        day_element = fixture[0][-1][-1][-1]
        self.assertEqual(str(int(expected_date.strftime('%s')) // (ONE_DAY)), day_element.attrib['date'])
