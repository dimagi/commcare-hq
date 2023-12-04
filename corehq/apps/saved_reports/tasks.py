import re
from datetime import datetime, timedelta
from urllib.parse import unquote

from django.conf import settings
from django.http import HttpRequest
from django.utils.translation import gettext as _

import six
from celery.schedules import crontab
from couchdbkit import ResourceNotFound

from dimagi.utils.django.email import LARGE_FILE_SIZE_ERROR_CODES
from dimagi.utils.logging import notify_exception
from dimagi.utils.web import json_request

from corehq.apps.celery import periodic_task, task
from corehq.apps.reports.tasks import export_all_rows_task
from corehq.apps.saved_reports.exceptions import (
    UnsupportedScheduledReportError,
)
from corehq.apps.saved_reports.models import ReportConfig, ReportNotification
from corehq.apps.saved_reports.scheduled import (
    create_records_for_scheduled_reports,
)
from corehq.apps.users.models import CouchUser
from corehq.elastic import ESError
from corehq.util.decorators import serial_task
from corehq.util.log import send_HTML_email

from .exceptions import ReportNotFound
from .models import ScheduledReportLog


def send_delayed_report(report_id):
    """
    Sends a scheduled report, via celery background task.
    """
    try:
        report = ReportNotification.get(report_id)
    except ResourceNotFound:
        raise ReportNotFound

    domain = report.domain

    if (
        settings.SERVER_ENVIRONMENT == 'production'
        and any(re.match(pattern, domain) for pattern in settings.THROTTLE_SCHED_REPORTS_PATTERNS)
    ):
        # This is to prevent a few scheduled reports from clogging up
        # the background queue.
        # https://manage.dimagi.com/default.asp?270029#BugEvent.1457969
        send_report_throttled.delay(report_id)
    else:
        send_report.delay(report_id)


@task(serializer='pickle', queue='background_queue', ignore_result=True)
def send_report(notification_id):
    notification = ReportNotification.get(notification_id)

    # If the report's start date is later than today, return and do not send the email
    if notification.start_date and notification.start_date > datetime.today().date():
        return

    try:
        notification.send()
    except UnsupportedScheduledReportError:
        pass


@task(serializer='pickle', queue='send_report_throttled', ignore_result=True)
def send_report_throttled(notification_id):
    send_report(notification_id)


@periodic_task(
    run_every=crontab(hour="*", minute="*/15", day_of_week="*"),
    queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'),
)
def initiate_queue_scheduled_reports():
    queue_scheduled_reports()


@periodic_task(
    run_every=crontab(hour="5", minute="0", day_of_week="*"),
    queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'),
)
def purge_old_scheduled_report_logs():
    current_time = datetime.utcnow()
    EXPIRED_DATE = current_time - timedelta(weeks=12)
    ScheduledReportLog.objects.filter(timestamp__lt=EXPIRED_DATE).delete()


@serial_task('queue_scheduled_reports', queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def queue_scheduled_reports():
    for report_id in create_records_for_scheduled_reports():
        try:
            send_delayed_report(report_id)
        except ReportNotFound:
            # swallow the exception. If the report was deleted, it won't show up on future runs anyway
            pass


@task(serializer='pickle', bind=True, default_retry_delay=15 * 60, max_retries=10, acks_late=True)
def send_email_report(self, recipient_emails, domain, report_slug, report_type,
                      request_data, once, cleaned_data):
    """
    Function invokes send_HTML_email to email the html text report.
    If the report is too large to fit into email then a download link is
    sent via email to download report
    :Parameter recipient_list:
            list of recipient to whom email is to be sent
    :Parameter domain:
            domain name
    :Parameter report_slug:
            report slug
    :Parameter report_type:
            type of the report
    :Parameter request_data:
            Dict containing request data
    :Parameter once
            boolean argument specifying whether the report is once off report
            or scheduled report
    :Parameter cleaned_data:
            Dict containing cleaned data from the submitted form
    """
    from corehq.apps.reports.views import (
        _render_report_configs,
        render_full_report_notification,
    )

    user_id = request_data['couch_user']
    couch_user = CouchUser.get_by_user_id(user_id)

    mock_request = HttpRequest()
    mock_request.method = 'GET'
    mock_request.GET = request_data['GET']

    config = create_config_for_email(report_type, report_slug, user_id, domain, request_data)
    subject = cleaned_data['subject'] or _("Email report from CommCare HQ")

    try:
        report_text = _render_report_configs(
            mock_request, [config], domain, user_id, couch_user, True, lang=couch_user.language,
            notes=cleaned_data['notes'], once=once
        )[0]
        body = render_full_report_notification(None, report_text).content

        for recipient in recipient_emails:
            send_HTML_email(subject, recipient,
                            body, smtp_exception_skip_list=LARGE_FILE_SIZE_ERROR_CODES,
                            domain=domain, use_domain_gateway=True,)

    except Exception as er:
        notify_exception(
            None,
            message="Encountered error while generating report or sending email",
            details={
                'subject': subject,
                'recipients': str(recipient_emails),
                'error': er,
            }
        )
        if getattr(er, 'smtp_code', None) in LARGE_FILE_SIZE_ERROR_CODES or type(er) == ESError:
            # If the email doesn't work because it is too large to fit in the HTML body,
            # send it as an excel attachment.
            report_state = {
                'request': request_data,
                'request_params': json_request(request_data['GET']),
                'domain': domain,
                'context': {},
            }
            export_all_rows_task(config.report, report_state, recipient_list=recipient_emails)
        else:
            self.retry(exc=er)


def create_config_for_email(report_type, report_slug, user_id, domain, request_data):
    config = ReportConfig()

    # see ReportConfig.query_string()
    object.__setattr__(config, '_id', 'dummy')
    config.name = _("Emailed report")
    config.report_type = report_type
    config.report_slug = report_slug
    config.owner_id = user_id
    config.domain = domain

    GET = dict(six.iterlists(request_data['GET']))
    exclude = ['startdate', 'enddate', 'subject', 'send_to_owner', 'notes', 'recipient_emails']
    filters = {}
    for field in GET:
        if field == 'params':
            params = unquote(GET.get(field)[0])
            params = params.split('&')
            for param in params:
                key, value = tuple(param.split('=', 1))
                if key in filters:
                    filters[key] = filters[key] + [value] if isinstance(filters[key], list) \
                        else [filters[key]] + [value]
                else:
                    filters[key] = value
        if field not in exclude:
            filters[field] = GET.get(field) or filters[field]

    config.filters = filters

    if 'startdate' in config.filters and report_slug != 'project_health':
        config.start_date = datetime.strptime(config.filters['startdate'], '%Y-%m-%d').date()
        if 'enddate' in config.filters:
            config.date_range = 'range'
            config.end_date = datetime.strptime(config.filters['enddate'], '%Y-%m-%d').date()
        else:
            config.date_range = 'since'

    return config
