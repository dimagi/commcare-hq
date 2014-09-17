from datetime import date, timedelta
from xml.etree import ElementTree
from sqlagg import SumColumn, filters
from sqlagg.base import AliasColumn
from sqlagg.columns import SimpleColumn
from corehq.apps.reports.sqlreport import AggregateColumn
from casexml.apps.case.tests.util import check_xml_line_by_line
from corehq.apps.callcenter.fixturegenerators import gen_fixture
from corehq.apps.callcenter.indicator_sets import SqlIndicatorSet
from corehq.apps.callcenter.tests.sql_fixture import load_fixture_test_data
from corehq.apps.reports.sqlreport import DatabaseColumn
from corehq.apps.users.models import CommCareUser
from django.test import TestCase


def _percentage(num, denom):
    if num is not None and denom is not None:
        return num / denom

    return 0


class TestIndicatorSet(SqlIndicatorSet):
    """
    Assumes SQL table with the following columns:
    * case (string): the case id
    * date (date): the date of the indicator grain
    * cases_updated (integer): number of cases updated by on date
    """
    name = 'call_center'
    table_name = 'call_center'

    def __init__(self, domain, user, group=None, keys=None):
        super(TestIndicatorSet, self).__init__(domain, user)
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
        cols = [
            DatabaseColumn("case", SimpleColumn('case'), format_fn=self.map_case, sortable=False)] \
            if self.group_by else []

        return cols + [
            DatabaseColumn('casesUpdatedInLastWeek', SumColumn('cases_updated'), sortable=False),
            DatabaseColumn('casesUpdatedInWeekPrior', SumColumn('cases_updated',
                                                                filters=[
                                                                    filters.GTE('date', '2weekago'),
                                                                    filters.LT('date', 'weekago')
                                                                ],
                                                                alias='casesUpdatedInWeekPrior'),
                           sortable=False),
            AggregateColumn('averageDurationPerCase', _percentage,
                            [SumColumn('duration'), AliasColumn('cases_updated')],
                            sortable=False)
        ]

    def map_case(self, value):
        return value[::-1]


class IndicatorFixtureTest(TestCase):
    @classmethod
    def setUpClass(cls):
        load_fixture_test_data()
        cls.user = CommCareUser.create('qwerty', 'rudolph', '***')
        cls.config = dict(columns=['casesUpdatedInLastWeek', 'casesUpdatedInWeekPrior'])

    @classmethod
    def tearDownClass(cls):
        cls.user.delete()

    def test_callcenter_group(self):
        fixture = gen_fixture(self.user, TestIndicatorSet('domain', 'user', 'case'))
        check_xml_line_by_line(self, """
        <fixture id="indicators:call_center" user_id="{userid}">
            <indicators>
                <case id="321">
                    <casesUpdatedInLastWeek>3</casesUpdatedInLastWeek>
                    <casesUpdatedInWeekPrior>4</casesUpdatedInWeekPrior>
                    <averageDurationPerCase>7</averageDurationPerCase>
                </case>
            </indicators>
        </fixture>
        """.format(userid=self.user.user_id), ElementTree.tostring(fixture))

    def test_callcenter_no_group(self):
        fixture = gen_fixture(self.user, TestIndicatorSet('domain', 'user'))
        check_xml_line_by_line(self, """
        <fixture id="indicators:call_center" user_id="{userid}">
            <indicators>
                <casesUpdatedInLastWeek>3</casesUpdatedInLastWeek>
                <casesUpdatedInWeekPrior>4</casesUpdatedInWeekPrior>
                <averageDurationPerCase>7</averageDurationPerCase>
            </indicators>
        </fixture>
        """.format(userid=self.user.user_id), ElementTree.tostring(fixture))

    def test_callcenter_keys(self):
        fixture = gen_fixture(self.user, TestIndicatorSet('domain', 'user', 'case', [['123'], ['456']]))
        check_xml_line_by_line(self, """
        <fixture id="indicators:call_center" user_id="{userid}">
            <indicators>
                <case id="321">
                    <casesUpdatedInLastWeek>3</casesUpdatedInLastWeek>
                    <casesUpdatedInWeekPrior>4</casesUpdatedInWeekPrior>
                    <averageDurationPerCase>7</averageDurationPerCase>
                </case>
                <case id="654">
                    <casesUpdatedInLastWeek>0</casesUpdatedInLastWeek>
                    <casesUpdatedInWeekPrior>0</casesUpdatedInWeekPrior>
                    <averageDurationPerCase>0</averageDurationPerCase>
                </case>
            </indicators>
        </fixture>
        """.format(userid=self.user.user_id), ElementTree.tostring(fixture))
