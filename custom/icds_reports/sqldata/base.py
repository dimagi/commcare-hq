from __future__ import absolute_import, unicode_literals

import json
import uuid

from django.core.serializers.json import DjangoJSONEncoder

from sqlalchemy.dialects import postgresql

from corehq.apps.reports.sqlreport import DatabaseColumn, SqlData
from corehq.toggles import ICDS_COMPARE_QUERIES_AGAINST_CITUS, NAMESPACE_OTHER


class IcdsSqlData(SqlData):
    engine_id = 'icds-ucr'

    def get_data(self, start=None, limit=None):
        from custom.icds_reports.tasks import run_citus_experiment_raw_sql

        query_context = self.query_context()
        for qm in query_context.query_meta.values():
            query = qm._build_query().compile(dialect=postgresql.dialect())
            if ICDS_COMPARE_QUERIES_AGAINST_CITUS.enabled(uuid.uuid4().hex, NAMESPACE_OTHER):
                params = json.loads(json.dumps(self.filter_values, cls=DjangoJSONEncoder))
                run_citus_experiment_raw_sql.delay(query, params, data_source=self.__class__.__name__)
        return super(IcdsSqlData, self).get_data(start, limit)


class ICDSDatabaseColumn(DatabaseColumn):
    def get_raw_value(self, row):
        return (self.view.get_value(row) or '') if row else ''
