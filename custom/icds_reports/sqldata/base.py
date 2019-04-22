from __future__ import absolute_import, unicode_literals

from corehq.apps.reports.sqlreport import DatabaseColumn, SqlData


class IcdsSqlData(SqlData):
    engine_id = 'icds-ucr'


class ICDSDatabaseColumn(DatabaseColumn):
    def get_raw_value(self, row):
        return (self.view.get_value(row) or '') if row else ''
