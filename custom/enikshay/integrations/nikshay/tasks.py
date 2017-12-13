from __future__ import absolute_import
from celery.task import periodic_task
from celery.schedules import crontab
from django.core.management import call_command


@periodic_task(run_every=crontab(minute="0", hour="0"), queue='background_queue')
def send_nikshay_registration_notification_report():
    # send notification time report each midnight
    call_command('nikshay_registration_notification_time_report', 1, email=["mkangia@dimagi.com"])
