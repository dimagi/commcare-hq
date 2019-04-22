from __future__ import absolute_import, unicode_literals

import uuid

from corehq.apps.reports.sqlreport import DatabaseColumn, SqlData
from corehq.toggles import ICDS_COMPARE_QUERIES_AGAINST_CITUS, NAMESPACE_OTHER


class IcdsSqlData(SqlData):
    engine_id = 'icds-ucr'

    def get_data(self, start=None, limit=None):
        from custom.icds_reports.tasks import run_citus_experiment_raw_sql

        for query in self.get_sql_queries():
            if ICDS_COMPARE_QUERIES_AGAINST_CITUS.enabled(uuid.uuid4().hex, NAMESPACE_OTHER):
                run_citus_experiment_raw_sql.delay(query, data_source=self.__class__.__name__)
        return super(IcdsSqlData, self).get_data(start, limit)


class ICDSDatabaseColumn(DatabaseColumn):
    def get_raw_value(self, row):
        return (self.view.get_value(row) or '') if row else ''
