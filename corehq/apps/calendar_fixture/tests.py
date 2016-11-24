import uuid
from xml.etree import ElementTree
from datetime import date
from django.test import TestCase
from casexml.apps.case.xml import V2
from corehq.apps.calendar_fixture.fixture_provider import calendar_fixture_generator
from corehq.apps.users.models import CommCareUser
from corehq.toggles import CUSTOM_CALENDAR_FIXTURE
from corehq.util.decorators import temporarily_enable_toggle


class TestFixture(TestCase):

    def test_nothing(self):
        user = CommCareUser(_id=uuid.uuid4().hex, domain='not-enabled')
        self.assertEqual([], calendar_fixture_generator(user, V2))

    @temporarily_enable_toggle(CUSTOM_CALENDAR_FIXTURE, 'test-calendar')
    def test_fixture_enabled(self):
        user = CommCareUser(_id=uuid.uuid4().hex, domain='test-calendar')
        fixture = calendar_fixture_generator(user, V2)[0]
        self.assertEqual(user._id, fixture.attrib['user_id'])
        self._check_first_date(fixture, date(2016, 1, 1))
        self._check_last_date(fixture, date(2016, 12, 31))

    def _check_first_date(self, fixture, expected_date):
        year_element = fixture[0][0]
        self.assertEqual(str(expected_date.year), year_element.attrib['number'])
        month_element = fixture[0][0][0]
        self.assertEqual(str(expected_date.month), month_element.attrib['number'])
        day_element = fixture[0][0][0][0]
        self.assertEqual(str(int(expected_date.strftime('%s')) / (60 * 60 * 24)), day_element.attrib['date'])

    def _check_last_date(self, fixture, expected_date):
        year_element = fixture[0][-1]
        self.assertEqual(str(expected_date.year), year_element.attrib['number'])
        month_element = fixture[0][-1][-1]
        self.assertEqual(str(expected_date.month), month_element.attrib['number'])
        day_element = fixture[0][-1][-1][-1]
        self.assertEqual(str(int(expected_date.strftime('%s')) / (60 * 60 * 24)), day_element.attrib['date'])
