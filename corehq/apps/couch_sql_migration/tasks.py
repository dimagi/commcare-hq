from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.util.datadog.gauges import datadog_gauge_task
from celery.schedules import crontab
from corehq.apps.couch_sql_migration.progress import total_couch_domains_remaining


datadog_gauge_task('commcare.couch_sql_migration.total_remaining',
                   total_couch_domains_remaining,
                   run_every=crontab(minute=0, hour=10))
