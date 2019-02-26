from __future__ import absolute_import
from __future__ import unicode_literals

from celery.schedules import crontab
from celery.task import periodic_task

from corehq.apps.es import DomainES, filters, aggregations
from corehq.util.datadog.gauges import datadog_gauge


@periodic_task(queue='background_queue', run_every=crontab(minute=0, hour=10),
               acks_late=True, ignore_result=True)
def couch_sql_migration_stats():
    result = (
        DomainES()
        .filter(filters.term('use_sql_backend', False))
        .remove_default_filters()
        .aggregations([
            aggregations.SumAggregation('cases', 'cp_n_cases'),
            aggregations.SumAggregation('forms', 'cp_n_forms'),
        ])
        .size(0).run()
    )

    datadog_gauge('commcare.couch_sql_migration.domains_remaining', int(result.total))
    datadog_gauge('commcare.couch_sql_migration.forms_remaining', int(result.aggregations.forms.value))
    datadog_gauge('commcare.couch_sql_migration.cases_remaining', int(result.aggregations.cases.value))
