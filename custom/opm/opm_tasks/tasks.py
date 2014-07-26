"""
Celery tasks to save a snapshot of the reports each month
"""
import datetime
import logging
import traceback

from celery.task import periodic_task
from celery.schedules import crontab
from celery.task.base import task

from django.conf import settings

from corehq.apps.users.models import WebUser
from custom.opm.opm_tasks import DEVELOPERS_EMAILS

from ..opm_reports.reports import (BeneficiaryPaymentReport,
                                   IncentivePaymentReport, MetReport, get_report, this_month_if_none)
from ..opm_reports.constants import DOMAIN
from .models import OpmReportSnapshot
from dimagi.utils.django.email import send_HTML_email


def prepare_snapshot(month, year, ReportClass, block=None, lang=None):
    existing = OpmReportSnapshot.by_month(month, year, ReportClass.__name__, block)
    assert existing is None, \
        "Existing report found for %s/%s at %s" % (month, year, existing._id)
    report = get_report(ReportClass, month, year, block, lang)
    snapshot = OpmReportSnapshot(
        domain=DOMAIN,
        month=report.month,
        year=report.year,
        block=report.block,
        report_class=ReportClass.__name__,
        headers=report.headers,
        slugs=report.slugs,
        rows=report.rows,
        visible_cols=report.visible_cols

    )
    snapshot.save()
    return snapshot


def save_report(ReportClass, month=None, year=None):
    """
    Save a snapshot of the report.
    Pass a month and year to save an arbitrary month.
    """
    month, year = this_month_if_none(month, year)
    if ReportClass.__name__ == "MetReport":
        for block in ['atri', 'wazirganj']:
            snapshot = prepare_snapshot(month, year, ReportClass, block, 'en')
    else:
        snapshot = prepare_snapshot(month, year, ReportClass)
    return snapshot


@periodic_task(
    run_every=crontab(hour=23, minute=55, day_of_month="28-31"),
    queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery')
)
def snapshot():
    now = datetime.datetime.now()
    tomorrow_date = now + datetime.timedelta(days=1)
    if tomorrow_date.month > now.month:
        save_ip_report.delay(IncentivePaymentReport, now.month, now.year)
        save_bp_report.delay(BeneficiaryPaymentReport, now.month, now.year)
        save_met_report.delay(MetReport, now.month, now.year)


def get_admins_emails():
    def get_role_or_none(user):
        role = user.get_role(DOMAIN, False, False)
        if role:
            return role.name
        return None

    return map(lambda user: user.get_email(),
               filter(lambda user: get_role_or_none(user) == 'Succeed Admin',
               WebUser.by_domain(DOMAIN)))

def send_emails(title, msg):
    emails = get_admins_emails()
    for email in DEVELOPERS_EMAILS + emails:
        send_HTML_email(title, email, msg,
                        email_from=settings.DEFAULT_FROM_EMAIL)


def save(report, f, month, year):
    try:
        snapshot = save_report(report, month, year)
        title = "[commcarehq] {0} saving success.".format(report.__name__)
        msg = "Saving {0} to doc {1} was finished successfully".format(report.__name__, snapshot._id)
        send_emails(title, msg)
        logging.info(msg)
    except AssertionError as ae:
        logging.error(ae.message)
    except Exception as e:
        tb = traceback.format_exc()
        title = "[commcarehq] {0} saving error.".format(report.__name__)
        msg = "Error in saving doc {0} due to {1}. {2}".format(report.__name__, e.message, tb)
        send_emails(title, msg)
        logging.error(msg)
        f.retry(exc=e)


@task(default_retry_delay=240 * 60, max_retries=12)
def save_ip_report(report, month, year):
    save(report, save_ip_report, month, year)


@task(default_retry_delay=240 * 60, max_retries=12)
def save_bp_report(report, month, year):
    save(report, save_bp_report, month, year)


@task(default_retry_delay=240 * 60, max_retries=12)
def save_met_report(report, month, year):
    save(report, save_met_report, month, year)