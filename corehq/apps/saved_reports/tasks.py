import re
from datetime import datetime, timedelta

from django.conf import settings
from django.http import HttpRequest
from django.http.request import QueryDict
from django.utils.translation import ugettext as _

import six
from celery.schedules import crontab
from celery.task import periodic_task, task

from dimagi.utils.django.email import LARGE_FILE_SIZE_ERROR_CODES
from dimagi.utils.web import json_request
from dimagi.utils.logging import notify_exception

from corehq.apps.reports.tasks import export_all_rows_task
from corehq.apps.saved_reports.exceptions import (
    UnsupportedScheduledReportError,
)
from couchdbkit import ResourceNotFound
from corehq.apps.saved_reports.models import ReportConfig, ReportNotification
from corehq.apps.saved_reports.scheduled import (
    create_records_for_scheduled_reports,
)
from corehq.apps.users.models import CouchUser
from corehq.elastic import ESError
from corehq.util.dates import iso_string_to_datetime
from corehq.util.decorators import serial_task
from corehq.util.log import send_HTML_email

from .models import ScheduledReportLog
from .exceptions import ReportNotFound


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


@task(queue='background_queue', ignore_result=True)
def send_report(notification_id):
    notification = ReportNotification.get(notification_id)

    # If the report's start date is later than today, return and do not send the email
    if notification.start_date and notification.start_date > datetime.today().date():
        return

    try:
        notification.send()
    except UnsupportedScheduledReportError:
        pass


@task(queue='send_report_throttled', ignore_result=True)
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


@task(bind=True, default_retry_delay=15 * 60, max_retries=10, acks_late=True)
def send_email_report(
    self,
    recipient_list,
    domain,
    report_slug,
    report_type,
    request_data,
    is_once_off,
    subject='',
    notes='',
):
    """
    Function invokes send_HTML_email to email the html text report.
    If the report is too large to fit into email then a download link is
    sent via email to download report
    """
    from corehq.apps.reports.views import _render_report_configs, render_full_report_notification

    user_id = request_data['couch_user']
    couch_user = CouchUser.get_by_user_id(user_id)

    mock_request = HttpRequest()
    GET_data = QueryDict('', mutable=True)
    GET_data.update(request_data['GET'])
    mock_request.method = 'GET'
    mock_request.GET = GET_data

    request_params = request_data['GET'].dict()
    config = _get_report_config(
        domain,
        report_type,
        report_slug,
        user_id,
        date_range='range' if 'enddate' in request_params else 'since',
        start_date=request_params.get('startdate', request_data['startdate']),
        end_date=request_params.get('enddate'),
        request_params=request_params,
    )

    # TODO: This just makes request_data['GET'] mutable, but we don't
    #       ever change it
    # request_data['GET'] = GET_data
    dedup_recipients = set(recipient_list)
    try:
        report_text = _render_report_configs(
            mock_request, [config], domain, user_id, couch_user, True, lang=couch_user.language,
            notes=notes, once=is_once_off
        )[0]
        body = render_full_report_notification(None, report_text).content

        for recipient in dedup_recipients:
            send_HTML_email(subject, recipient,
                            body, email_from=settings.DEFAULT_FROM_EMAIL,
                            smtp_exception_skip_list=LARGE_FILE_SIZE_ERROR_CODES)

    except Exception as er:
        notify_exception(
            None,
            message="Encountered error while generating report or sending email",
            details={
                'subject': subject,
                'recipients': str(recipient_list),
                'error': er,
            }
        )
        if getattr(er, 'smtp_code', None) in LARGE_FILE_SIZE_ERROR_CODES or type(er) == ESError:
            # If the email doesn't work because it is too large to fit in the HTML body,
            # send it as an excel attachment.
            report_state = {
                'request': request_data,
                'domain': domain,
                'context': {},
                'request_params': json_request(request_data['GET'])
            }
            export_all_rows_task(config.report.slug, report_state, recipient_list=recipient_list)
        else:
            self.retry(exc=er)


def _get_report_config(
    domain,
    report_type,
    report_slug,
    user_id,
    *,
    date_range,
    start_date,
    end_date=None,
    request_params,
):
    exclude = {
        'startdate',
        'enddate',
        'subject',
        'send_to_owner',
        'notes',
        'recipient_emails',
    }
    filters = {k: v for k, v in request_params.items() if k not in exclude}

    return ReportConfig(
        # "config_id" is omitted from ReportConfig.query_string if its
        # value is "dummy". See ReportConfig.query_string for details.
        _id='dummy',

        domain=domain,
        name=_("Emailed report"),
        report_type=report_type,
        report_slug=report_slug,
        owner_id=user_id,
        date_range=date_range,
        start_date=iso_string_to_datetime(start_date),
        end_date=iso_string_to_datetime(end_date) if end_date else None,
        filters=filters,
    )
