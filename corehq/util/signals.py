import logging
from celery.signals import task_failure
from django.conf import settings


@task_failure.connect
def log_celery_task_exception(task_id, exception, traceback, einfo, *args, **kwargs):
    if settings.environment == 'icds':
        django_logger = logging.getLogger('django.request')
        django_logger.error(u"Exception - {}".format(exception.message))
