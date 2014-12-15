from collections import OrderedDict
from datetime import datetime, date, time, timedelta
from xml.etree import ElementTree
import pytz
from casexml.apps.case.tests.util import check_xml_line_by_line
from casexml.apps.phone.models import SyncLog
from corehq.apps.callcenter.fixturegenerators import gen_fixture, should_sync
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import CommCareUser
from django.test import SimpleTestCase


class MockIndicatorSet(object):
    def __init__(self, name, indicators):
        self.name = name
        self.indicators = indicators

    def get_data(self):
        return self.indicators

    @property
    def reference_date(self):
        return datetime.strptime("2014-01-01T00:00:00", "%Y-%m-%dT%H:%M:%S")


class CallcenterFixtureTests(SimpleTestCase):
    def test_callcenter_fixture_format(self):
        user = CommCareUser(_id='123')
        indicator_set = MockIndicatorSet(name='test', indicators=OrderedDict([
            ('user_case1', {'i1': 1, 'i2': 2}),
            ('user_case2', {'i1': 0, 'i2': 3})
        ]))

        fixture = gen_fixture(user, indicator_set)
        check_xml_line_by_line(self, """
        <fixture date="2014-01-01T00:00:00" id="indicators:test" user_id="{userid}">
            <indicators>
                <case id="user_case1">
                    <i1>1</i1>
                    <i2>2</i2>
                </case>
                <case id="user_case2">
                    <i1>0</i1>
                    <i2>3</i2>
                </case>
            </indicators>
        </fixture>
        """.format(userid=user.user_id), ElementTree.tostring(fixture))

    def test_should_sync_none(self):
        self.assertTrue(should_sync(None, None))

    def test_should_sync_no_date(self):
        self.assertTrue(should_sync(None, SyncLog()))

    def test_should_sync_false(self):
        domain = Domain(name='test', default_timezone='UTC')
        last_sync = datetime.combine(date.today(), time())  # today at 00:00:00
        self.assertFalse(should_sync(domain, SyncLog(date=last_sync)))

    def test_should_sync_true(self):
        domain = Domain(name='test', default_timezone='UTC')
        last_sync = datetime.combine(date.today() - timedelta(days=1), time(23, 59, 59))  # yesterday at 23:59:59
        self.assertTrue(should_sync(domain, SyncLog(date=last_sync)))

    def test_should_sync_timezone(self):
        domain = Domain(name='test', default_timezone='Africa/Johannesburg')
        # yesterday at 21:59:59 = yesterday at 23:59:59 locally
        last_sync = datetime.combine(date.today() - timedelta(days=1), time(21, 59, 59)).replace(tzinfo=pytz.utc)
        # yesterday at 21:59:59 = today at 00:00:00 locally
        utcnow = datetime.combine(date.today() - timedelta(days=1), time(22, 00, 00)).replace(tzinfo=pytz.utc)
        self.assertTrue(should_sync(domain, SyncLog(date=last_sync), utcnow=utcnow))

        domain = Domain(name='test', default_timezone='UTC')
        self.assertFalse(should_sync(domain, SyncLog(date=last_sync), utcnow=utcnow))
