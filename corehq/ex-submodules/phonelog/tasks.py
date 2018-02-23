from __future__ import absolute_import

from datetime import datetime, timedelta

import requests
from celery.schedules import crontab
from celery.task import periodic_task, task
from django.conf import settings
from django.db import connection

from corehq.toggles import SUMOLOGIC_LOGS, NAMESPACE_OTHER
from phonelog.models import ForceCloseEntry, UserEntry, UserErrorEntry
from phonelog.utils import SumoLogicLog


@periodic_task(run_every=crontab(minute=0, hour=0), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def purge_old_device_report_entries():
    max_age = datetime.utcnow() - timedelta(days=settings.DAYS_TO_KEEP_DEVICE_LOGS)
    with connection.cursor() as cursor:
        partitoned_db_format = 'phonelog_daily_partitioned_devicereportentry_y%Yd%j'
        table_to_drop = (max_age - timedelta(days=1)).strftime(partitoned_db_format)
        cursor.execute("DROP TABLE {}".format(table_to_drop))
    UserErrorEntry.objects.filter(server_date__lt=max_age).delete()
    ForceCloseEntry.objects.filter(server_date__lt=max_age).delete()
    UserEntry.objects.filter(server_date__lt=max_age).delete()


@task
def send_device_logs_to_sumologic(domain, xform):
    url = getattr(settings, 'SUMOLOGIC_URL', None)
    if url and SUMOLOGIC_LOGS.enabled(xform.form_data.get('device_id'), NAMESPACE_OTHER):
        for fmt in ['log', 'user_error', 'force_close']:
            headers = {"X-Sumo-Category": "{env}/{domain}/{fmt}".format(
                env=_get_sumologic_environment(),
                domain=domain,
                fmt=fmt,
            )}
            data = getattr(SumoLogicLog(domain, xform), "{}_subreport".format(fmt))()
            requests.post(url, data=data, headers=headers)


def _get_sumologic_environment():
    """
    https://docs.google.com/document/d/18sSwv2GRGepOIHthC6lxQAh_aUYgDcTou6w9jL2976o/edit#bookmark=id.ao4j7x5tjvt7  # noqa
    """
    if settings.SERVER_ENVIRONMENT in settings.ICDS_ENVS:
        return 'cas'
    if settings.SERVER_ENVIRONMENT == 'softlayer':
        return 'india'
    if settings.SERVER_ENVIRONMENT == 'production':
        return 'prod'

    return 'test-env'
