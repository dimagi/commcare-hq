import calendar
from datetime import date

from django.conf import settings
from django.core.management import call_command
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _

from dateutil.relativedelta import relativedelta

from couchexport.models import Format
from dimagi.utils import web
from soil.util import expose_cached_download

from celery.schedules import crontab
from corehq.apps.hqwebapp.tasks import send_html_email_async
from corehq.util.celery_utils import periodic_task_on_envs
from corehq.util.files import file_extention_from_filename


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
            Could not generate the montly SMS report for ICDS.
            The error has been notified. Please report as an issue for quick followup
        """)
        send_html_email_async.delay(subject, recipients, message,
                                    email_from=settings.DEFAULT_FROM_EMAIL)
        raise e
