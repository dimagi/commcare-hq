from corehq.apps.reports.sqlreport import DatabaseColumn, SqlData
from corehq.sql_db.connections import ICDS_UCR_CITUS_ENGINE_ID


class IcdsSqlData(SqlData):
    @property
    def engine_id(self):
        return ICDS_UCR_CITUS_ENGINE_ID


class ICDSDatabaseColumn(DatabaseColumn):
    def get_raw_value(self, row):
        return (self.view.get_value(row) or '') if row else ''
