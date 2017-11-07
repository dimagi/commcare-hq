from __future__ import absolute_import
from sqlagg.columns import MaxColumn
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
        return ['year']

    @property
    def filters(self):
        return [
            EQ('year', 'year')
        ]

    @property
    def columns(self):
        return [
            DatabaseColumn('week', MaxColumn('week'))
        ]
