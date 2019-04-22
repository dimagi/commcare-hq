from __future__ import absolute_import, unicode_literals

import uuid

from django.db.models.manager import BaseManager
from django.db.models.query import QuerySet

from corehq.toggles import ICDS_COMPARE_QUERIES_AGAINST_CITUS, NAMESPACE_OTHER


class CitusComparisonQuerySet(QuerySet):
    def _fetch_all(self):
        from custom.icds_reports.tasks import run_citus_experiment_raw_sql
        if ICDS_COMPARE_QUERIES_AGAINST_CITUS.enabled(uuid.uuid4().hex, NAMESPACE_OTHER):
            run_citus_experiment_raw_sql.delay(str(self.query), data_source=self.model.__name__)
        super(CitusComparisonQuerySet, self)._fetch_all()


class CitusComparisonManager(BaseManager.from_queryset(CitusComparisonQuerySet)):
    pass
