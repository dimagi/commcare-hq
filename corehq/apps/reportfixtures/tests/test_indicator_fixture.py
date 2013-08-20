from datetime import date, timedelta
from xml.etree import ElementTree
from sqlagg import SumColumn
from sqlagg.columns import SimpleColumn
from casexml.apps.case.tests.util import check_xml_line_by_line
from corehq.apps.reportfixtures.fixturegenerators import gen_fixture
from corehq.apps.reportfixtures.indicator_sets import SqlIndicatorSet
from corehq.apps.reportfixtures.tests.sql_fixture import load_data
from corehq.apps.reports.sqlreport import DatabaseColumn
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

    def __init__(self, domain, user, group=None, keys=None):
        super(CallCenter, self).__init__(domain, user)
        self.group = group
        self.test_keys = keys

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
        return [self.group] if self.group else []

    @property
    def keys(self):
        return self.test_keys

    @property
    def columns(self):
        cols = [DatabaseColumn("case", SimpleColumn('case'), format_fn=self.map_case, sortable=False)] if self.group_by else []
        return cols + [
            DatabaseColumn('casesUpdatedInLastWeek', SumColumn('cases_updated'), sortable=False),
            DatabaseColumn('casesUpdatedInWeekPrior', SumColumn('cases_updated',
                                                                filters=['date >= :2weekago', 'date < :weekago'],
                                                                alias='casesUpdatedInWeekPrior'),
                           sortable=False),
        ]

    def map_case(self, value):
        return value[::-1]


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
        fixture = gen_fixture(self.user, CallCenter('domain', 'user', 'case'))
        check_xml_line_by_line(self, """
        <fixture id="indicators:call_center" user_id="{userid}">
            <indicators>
                <case id="321">
                    <casesUpdatedInLastWeek>3</casesUpdatedInLastWeek>
                    <casesUpdatedInWeekPrior>4</casesUpdatedInWeekPrior>
                </case>
            </indicators>
        </fixture>
        """.format(userid=self.user.user_id), ElementTree.tostring(fixture))

    def test_callcenter_no_group(self):
        fixture = gen_fixture(self.user, CallCenter('domain', 'user'))
        check_xml_line_by_line(self, """
        <fixture id="indicators:call_center" user_id="{userid}">
            <indicators>
                <casesUpdatedInLastWeek>3</casesUpdatedInLastWeek>
                <casesUpdatedInWeekPrior>4</casesUpdatedInWeekPrior>
            </indicators>
        </fixture>
        """.format(userid=self.user.user_id), ElementTree.tostring(fixture))

    def test_callcenter_keys(self):
        fixture = gen_fixture(self.user, CallCenter('domain', 'user', 'case', [['123'], ['456']]))
        check_xml_line_by_line(self, """
        <fixture id="indicators:call_center" user_id="{userid}">
            <indicators>
                <case id="321">
                    <casesUpdatedInLastWeek>3</casesUpdatedInLastWeek>
                    <casesUpdatedInWeekPrior>4</casesUpdatedInWeekPrior>
                </case>
                <case id="654">
                    <casesUpdatedInLastWeek>0</casesUpdatedInLastWeek>
                    <casesUpdatedInWeekPrior>0</casesUpdatedInWeekPrior>
                </case>
            </indicators>
        </fixture>
        """.format(userid=self.user.user_id), ElementTree.tostring(fixture))
