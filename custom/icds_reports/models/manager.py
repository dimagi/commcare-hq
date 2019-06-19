from __future__ import absolute_import, unicode_literals

import json
import uuid

from django.core.serializers.json import DjangoJSONEncoder
from django.db.models.manager import BaseManager
from django.db.models.query import QuerySet

from corehq.toggles import ICDS_COMPARE_QUERIES_AGAINST_CITUS, NAMESPACE_OTHER


class CitusComparisonQuerySet(QuerySet):
    def _fetch_all(self):
        from custom.icds_reports.utils.tasks import call_citus_experiment
        if (self._result_cache is None
                and ICDS_COMPARE_QUERIES_AGAINST_CITUS.enabled(uuid.uuid4().hex, NAMESPACE_OTHER)):
            query, params = self.query.sql_with_params()
            params = json.loads(json.dumps(params, cls=DjangoJSONEncoder))
            call_citus_experiment(query, params, data_source=self.model.__name__)
        super(CitusComparisonQuerySet, self)._fetch_all()


class CitusComparisonManager(BaseManager.from_queryset(CitusComparisonQuerySet)):
    pass
