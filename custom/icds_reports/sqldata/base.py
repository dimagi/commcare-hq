import json
import uuid

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder

from sqlalchemy.dialects import postgresql

from corehq.apps.reports.sqlreport import DatabaseColumn, SqlData
from corehq.sql_db.connections import ICDS_UCR_CITUS_ENGINE_ID, ICDS_UCR_ENGINE_ID
from corehq.sql_db.routers import forced_citus
from corehq.toggles import ICDS_COMPARE_QUERIES_AGAINST_CITUS, NAMESPACE_OTHER
from custom.icds_reports.utils.tasks import call_citus_experiment


class IcdsSqlData(SqlData):

    def get_data(self, start=None, limit=None):
        query_context = self.query_context()
        for qm in query_context.query_meta.values():
            query = qm._build_query().compile(dialect=postgresql.dialect())
            if ICDS_COMPARE_QUERIES_AGAINST_CITUS.enabled(uuid.uuid4().hex, NAMESPACE_OTHER):
                params = json.loads(json.dumps(self.filter_values, cls=DjangoJSONEncoder))
                call_citus_experiment(str(query), params, data_source=self.__class__.__name__)
        return super(IcdsSqlData, self).get_data(start, limit)

    @property
    def engine_id(self):
        if forced_citus() or getattr(settings, 'ICDS_USE_CITUS', False):
            return ICDS_UCR_CITUS_ENGINE_ID
        else:
            return ICDS_UCR_ENGINE_ID


class ICDSDatabaseColumn(DatabaseColumn):
    def get_raw_value(self, row):
        return (self.view.get_value(row) or '') if row else ''
