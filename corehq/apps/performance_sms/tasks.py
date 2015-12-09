from django.conf import settings

from celery.schedules import crontab
from celery.task import periodic_task
from corehq.apps.performance_sms.message_sender import send_messages_for_config
from .schedule import get_message_configs_at_this_hour


@periodic_task(run_every=crontab(hour="*", minute="0"),
               queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def fire_performance_sms():
    for config in get_message_configs_at_this_hour():
        send_messages_for_config(config)
