import calendar
from datetime import date, datetime

from django.conf import settings
from django.core.management import call_command
from django.db import connections, router
from django.db.models.signals import post_save
from django.db.transaction import atomic
from django.dispatch import receiver
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _

from celery.schedules import crontab
from dateutil.relativedelta import relativedelta

from corehq.util.metrics import metrics_counter
from couchexport.models import Format
from dimagi.utils import web
from soil.util import expose_cached_download

from corehq.apps.domain.models import Domain
from corehq.apps.hqwebapp.tasks import send_html_email_async
from corehq.apps.sms.const import DEFAULT_SMS_DAILY_LIMIT
from corehq.apps.sms.models import (
    SMS,
    DailyOutboundSMSLimitReached,
    MessagingEvent,
    MessagingSubEvent,
)
from corehq.util.celery_utils import periodic_task_on_envs, task
from corehq.util.files import file_extention_from_filename
from custom.icds_core.view_utils import is_icds_cas_project
from custom.icds.utils.custom_sms_report import CustomSMSReportTracker


@periodic_task_on_envs(settings.ICDS_ENVS, run_every=crontab(day_of_month='2', minute=0, hour=0), queue='sms_queue')
def send_monthly_sms_report():
    subject = _('Monthly SMS report')
    recipients = ['mshastri@dimagi.com', 'akaul@dimagi-associate.com', 'dsivaramakrishnan@dimagi.com',
                  'pgoyal@dimagi.com', 'asharma@dimagi.com']
    try:
        start_date = date.today().replace(day=1) - relativedelta(months=1)
        first_day, last_day = calendar.monthrange(start_date.year, start_date.month)
        end_date = start_date.replace(day=last_day)
        filename = call_command('get_icds_sms_usage', 'icds-cas', str(start_date), str(end_date))
        with open(filename, 'rb') as f:
            cached_download = expose_cached_download(
                f.read(), expiry=24 * 60 * 60, file_extension=file_extention_from_filename(filename),
                mimetype=Format.from_format(Format.XLS_2007).mimetype,
                content_disposition='attachment; filename="%s"' % filename)
        path = reverse('retrieve_download', kwargs={'download_id': cached_download.download_id})
        link = f"{web.get_url_base()}{path}?get_file"
        message = _("""
        Hi,
        Please download the sms report for last month at {link}.
        The report is available only till midnight today.
        """).format(link=link)
        send_html_email_async.delay(subject, recipients, message,
                                    email_from=settings.DEFAULT_FROM_EMAIL)
    except Exception as e:
        message = _("""
            Hi,
            Could not generate the monthly SMS report for ICDS.
            The error has been notified. Please report as an issue for quick followup
        """)
        send_html_email_async.delay(subject, recipients, message,
                                    email_from=settings.DEFAULT_FROM_EMAIL)
        raise e


@task
def send_custom_sms_report(start_date: str, end_date: str, email, domain):
    subject = _('Monthly SMS report')
    recipients = [email]

    try:
        filename = call_command('get_icds_sms_usage', 'icds-cas', start_date, end_date)

        with open(filename, 'rb') as f:
            cached_download = expose_cached_download(
                f.read(), expiry=24 * 60 * 60, file_extension=file_extention_from_filename(filename),
                mimetype=Format.from_format(Format.XLS_2007).mimetype,
                content_disposition='attachment; filename="%s"' % filename)
            path = reverse('retrieve_download', kwargs={'download_id': cached_download.download_id})
            link = f"{web.get_url_base()}{path}?get_file"
            message = _("""
            Hi,
            Please download the sms report for time frame {start_date} to {end_date} (inclusive) at {link}.
            The report is available only for next 24 hours.
            """).format(link=link, start_date=start_date, end_date=end_date)
            send_html_email_async.delay(subject, recipients, message,
                                        email_from=settings.DEFAULT_FROM_EMAIL)
    except Exception as e:
        message = _("""
            Hi,
            Could not generate the custom SMS report for ICDS.
            The error has been notified. Please report as an issue for quick followup
        """)
        send_html_email_async.delay(subject, recipients, message,
                                    email_from=settings.DEFAULT_FROM_EMAIL)
        raise e
    finally:
        report_tracker = CustomSMSReportTracker(domain)
        report_tracker.remove_report(start_date, end_date)


@receiver(post_save, sender=DailyOutboundSMSLimitReached)
def send_sms_limit_exceeded_alert(sender, instance, **kwargs):
    if is_icds_cas_project(instance.domain):
        domain_obj = Domain.get_by_name(instance.domain)
        subject = "SMS Daily Limit exceeded"
        recipients = [
            'ndube@dimagi.com',
            'dsivaramakrishnan@dimagi.com',
            'mshashtri@dimagi.com',
            'asharma@dimagi.com'
        ]
        if domain_obj:
            sms_daily_limit = domain_obj.get_daily_outbound_sms_limit()
            message = _("""
            Hi,
            This is to inform you that the Daily SMS limit for domain {domain} has exceeded for {date}.
            The sms limit at the time of sending this email was set to {sms_limit}
            """).format(domain=instance.domain, date=instance.date, sms_limit=sms_daily_limit)
        else:
            sms_daily_limit = DEFAULT_SMS_DAILY_LIMIT
            message = _("""
            Hi,
            This is to inform you that the Daily SMS limit for enviornment {env} has exceeded for {date}.
            The sms limit at the time of sending this email was set to {sms_limit}
            """).format(env=settings.SERVER_ENVIRONMENT, date=instance.date, sms_limit=sms_daily_limit)
        send_html_email_async.delay(subject, recipients, message,
                email_from=settings.DEFAULT_FROM_EMAIL)


@periodic_task_on_envs(settings.ICDS_ENVS, run_every=crontab(hour=20))
def delete_old_sms_events():
    end_date = datetime.utcnow() - relativedelta(years=1)
    delete_sms_events.delay(datetime.min, end_date)


@task
def delete_sms_events(start_date, end_date):
    db = router.db_for_write(SMS)
    with atomic(db), connections[db].cursor() as cursor:
        cursor.execute(
            f"""
            UPDATE {SMS._meta.db_table} sms
            SET messaging_subevent_id = NULL
            FROM {MessagingSubEvent._meta.db_table} as subevent
            LEFT JOIN {MessagingEvent._meta.db_table} as event ON event.id = subevent.parent_id
            WHERE sms.messaging_subevent_id = subevent.id and event.date between %s and %s
            """,
            [start_date, end_date]
        )

        cursor.execute(
            f"""
            DELETE FROM {MessagingSubEvent._meta.db_table} as subevent
            USING {MessagingEvent._meta.db_table} as event
            WHERE subevent.parent_id = event.id
            AND event.date between %s and %s
            """,
            [start_date, end_date]
        )
        metrics_counter('commcare.sms_events.deleted', cursor.rowcount, tags={'type': 'sub_event'})

        cursor.execute(
            f"""
            DELETE FROM {MessagingEvent._meta.db_table}
            WHERE date between %s and %s
            """,
            [start_date, end_date]
        )
        metrics_counter('commcare.sms_events.deleted', cursor.rowcount, tags={'type': 'event'})
