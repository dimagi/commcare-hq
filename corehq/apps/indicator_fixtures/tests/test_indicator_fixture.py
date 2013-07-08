from datetime import date, timedelta
from xml.etree import ElementTree
from sqlagg import SumColumn
from casexml.apps.case.tests.util import check_xml_line_by_line
from corehq.apps.indicator_fixtures.fixturegenerators import gen_fixture
from corehq.apps.indicator_fixtures.indicator_sets import SqlIndicatorSet
from corehq.apps.indicator_fixtures.tests.sql_fixture import load_data
from corehq.apps.users.models import CommCareUser
from django.test import TestCase


class CallCenter(SqlIndicatorSet):
    """
    Assumes SQL table with the following columns:
    * case (string): the case id
    * date (date): the date of the indicator grain
    * cases_updated (integer): number of cases updated by on date
    """
    name = 'call_center'
    table_name = 'call_center'

    def __init__(self, config, group):
        super(CallCenter, self).__init__(config)
        self.group = group

    @property
    def filters(self):
        return ['date between :weekago and :today']

    @property
    def filter_values(self):
        return {
            'today': date.today() - timedelta(days=1),
            'weekago': date.today() - timedelta(days=7),
            '2weekago': date.today() - timedelta(days=14),
        }

    @property
    def group_by(self):
        return self.group

    @property
    def available_columns(self):
        return [
            SumColumn('cases_updated', alias='casesUpdatedInLastWeek'),
            SumColumn('cases_updated',
                      filters=['date >= :2weekago', 'date < :weekago'],
                      alias='casesUpdatedInWeekPrior'),
        ]


class IndicatorFixtureTest(TestCase):
    @classmethod
    def setUpClass(cls):
        load_data()
        cls.user = CommCareUser.create('qwerty', 'rudolph', '***')
        cls.config = dict(columns=['casesUpdatedInLastWeek', 'casesUpdatedInWeekPrior'])

    @classmethod
    def tearDownClass(cls):
        cls.user.delete()

    def test_callcenter_group(self):
        fixture = gen_fixture(self.user, CallCenter(self.config, 'case'))
        check_xml_line_by_line(self, """
        <fixture id="indicators:call_center" user_id="{userid}">
            <indicators>
                <case id="123">
                    <casesUpdatedInLastWeek>3</casesUpdatedInLastWeek>
                    <casesUpdatedInWeekPrior>4</casesUpdatedInWeekPrior>
                </case>
            </indicators>
        </fixture>
        """.format(userid=self.user.user_id), ElementTree.tostring(fixture))

    def test_callcenter_no_group(self):
        fixture = gen_fixture(self.user, CallCenter(self.config, None))
        check_xml_line_by_line(self, """
        <fixture id="indicators:call_center" user_id="{userid}">
            <indicators>
                <casesUpdatedInLastWeek>3</casesUpdatedInLastWeek>
                <casesUpdatedInWeekPrior>4</casesUpdatedInWeekPrior>
            </indicators>
        </fixture>
        """.format(userid=self.user.user_id), ElementTree.tostring(fixture))

    def test_callcenter_columns(self):
        fixture = gen_fixture(self.user, CallCenter(dict(columns=['casesUpdatedInLastWeek']), None))
        check_xml_line_by_line(self, """
        <fixture id="indicators:call_center" user_id="{userid}">
            <indicators>
                <casesUpdatedInLastWeek>3</casesUpdatedInLastWeek>
            </indicators>
        </fixture>
        """.format(userid=self.user.user_id), ElementTree.tostring(fixture))
