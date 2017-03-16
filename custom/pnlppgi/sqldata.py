from sqlagg.columns import SimpleColumn
from sqlagg.filters import EQ

from corehq.apps.reports.sqlreport import SqlData, DatabaseColumn
from corehq.apps.userreports.util import get_table_name


class LastDataForYear(SqlData):

    @property
    def engine_id(self):
        return 'ucr'

    @property
    def table_name(self):
        return get_table_name(self.config['domain'], "malaria")

    @property
    def group_by(self):
        return ['week']

    @property
    def filters(self):
        return [
            EQ('year', 'year')
        ]

    @property
    def columns(self):
        return [
            DatabaseColumn('week', SimpleColumn('week'))
        ]
