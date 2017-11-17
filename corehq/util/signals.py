from __future__ import absolute_import
from dimagi.utils.logging import notify_exception
from celery.signals import task_failure
from django.conf import settings


@task_failure.connect
def log_celery_task_exception(task_id, exception, traceback, einfo, *args, **kwargs):
    notify_exception('Celery task failure', exec_info=einfo.exc_info)
