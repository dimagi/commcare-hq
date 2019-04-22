from __future__ import absolute_import, unicode_literals

from django.db.models.manager import BaseManager
from django.db.models.query import QuerySet


class CitusComparisonQuerySet(QuerySet):
    def _fetch_all(self):
        from custom.icds_reports.tasks import run_citus_experiment_raw_sql
        # TODO make setting to control how many queries to compare
        run_citus_experiment_raw_sql.delay(str(self.query))
        super(CitusComparisonQuerySet, self)._fetch_all()


class CitusComparisonManager(BaseManager.from_queryset(CitusComparisonQuerySet)):
    pass
