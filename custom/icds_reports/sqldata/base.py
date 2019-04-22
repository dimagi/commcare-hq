from __future__ import absolute_import, unicode_literals

from corehq.apps.reports.sqlreport import DatabaseColumn, SqlData


class IcdsSqlData(SqlData):
    engine_id = 'icds-ucr'

    def get_data(self, start=None, limit=None):
        from custom.icds_reports.tasks import run_citus_experiment_raw_sql

        for query in self.get_sql_queries():
            run_citus_experiment_raw_sql.delay(query)
        return super(IcdsSqlData, self).get_data(start, limit)


class ICDSDatabaseColumn(DatabaseColumn):
    def get_raw_value(self, row):
        return (self.view.get_value(row) or '') if row else ''
