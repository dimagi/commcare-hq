from django import test as unittest
from sqlagg.columns import SimpleColumn, SumColumn
from sqlagg.filters import EQFilter
from corehq.apps.reports.sqlreport import SqlData, DatabaseColumn, AggregateColumn

from .sql_fixture import load_data
from .sql_reports import combine_indicator

DOMAIN = "test"
format_string = "%Y-%m-%d"''

unity = lambda x: x

class UserDataSource(SqlData):
    table_name = "user_report_data"

    def __init__(self, config, keys=None, filters=None, group_by=None):
        super(UserDataSource, self).__init__(config)
        self._group_by = group_by
        self._filters = filters
        self._keys = keys

    @property
    def group_by(self):
        return self._group_by

    @property
    def filters(self):
        return self._filters

    @property
    def keys(self):
        return self._keys

    @property
    def usernames_demo(self):
        return {"user1": "Joe", "user2": "Bob", 'user3': "Gill"}

    def username(self, key):
        return self.usernames_demo[key]

    @property
    def columns(self):
        user = DatabaseColumn("Username", SimpleColumn("user"), format_fn=self.username)
        i_a = DatabaseColumn("Indicator A", SumColumn("indicator_a"), format_fn=unity)
        i_b = DatabaseColumn("Indicator B", SumColumn("indicator_b"), format_fn=unity)

        agg_c_d = AggregateColumn("C/D", combine_indicator,
                                  [SumColumn("indicator_c"), SumColumn("indicator_d")],
                                  format_fn=unity)

        aggregate_cols = [
            i_a,
            i_b,
            agg_c_d
        ]

        if self.group_by:
            return [user] + aggregate_cols
        else:
            return aggregate_cols


class ReportAPITest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        load_data()

    def test_basic(self):
        ds = UserDataSource({}, keys=[["user1"], ["user2"]], group_by=['user'])
        data = ds.get_data()
        self.assertEqual(data, [
            {
                'user': 'Bob',
                'indicator_a': 1,
                'indicator_b': 1,
                'cd': 50
            },
            {
                'user': 'Joe',
                'indicator_a': 1,
                'indicator_b': 1,
                'cd': 100
            }
        ])

    def test_filter(self):
        ds = UserDataSource(
            {'user_id': 'user2'},
            filters=[EQFilter('user', 'user_id')],
            keys=[["user2"]],
            group_by=['user']
        )
        data = ds.get_data(['indicator_a'])
        self.assertEqual(data, [
            {
                'indicator_a': 1,
            }
        ])