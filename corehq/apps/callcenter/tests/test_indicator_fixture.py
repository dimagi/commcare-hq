from collections import OrderedDict
from xml.etree import ElementTree
from casexml.apps.case.tests.util import check_xml_line_by_line
from corehq.apps.callcenter.fixturegenerators import gen_fixture
from corehq.apps.users.models import CommCareUser
from django.test import SimpleTestCase


class MockIndicatorSet(object):
    def __init__(self, name, indicators):
        self.name = name
        self.indicators = indicators

    def get_data(self):
        return self.indicators


class CallcenterFixtureTests(SimpleTestCase):
    def test_callcenter_fixture_format(self):
        user = CommCareUser(_id='123')
        indicator_set = MockIndicatorSet(name='test', indicators=OrderedDict([
            ('user_case1', {'i1': 1, 'i2': 2}),
            ('user_case2', {'i1': 0, 'i2': 3})
        ]))

        fixture = gen_fixture(user, indicator_set)
        check_xml_line_by_line(self, """
        <fixture id="indicators:test" user_id="{userid}">
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
