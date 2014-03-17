"""
Celery tasks to save a snapshot of the reports each month
"""
import logging

from celery.task import periodic_task
from celery.schedules import crontab
from django.conf import settings

from ..opm_reports.reports import (BeneficiaryPaymentReport,
    IncentivePaymentReport, get_report, last_if_none)
from ..opm_reports.constants import DOMAIN
from .models import OpmReportSnapshot


def save_report(ReportClass, month=None, year=None):
    """
    Save a snapshot of the report.
    Pass a month and year to save an arbitrary month.
    """
    month, year = last_if_none(month, year)
    existing = OpmReportSnapshot.by_month(month, year, ReportClass.__name__)
    assert existing is None, \
        "Existing report found for %s/%s at %s" % (month, year, existing._id)
    report = get_report(ReportClass, month, year)
    snapshot = OpmReportSnapshot(
        domain=DOMAIN,
        month=report.month,
        year=report.year,
        report_class=ReportClass.__name__,
        headers=report.headers,
        slugs=report.slugs,
        rows=report.rows,
    )
    snapshot.save()
    return snapshot


@periodic_task(
    run_every=crontab(hour=10, minute=1, day_of_month=1),
    queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery')
)
def snapshot():
    for report in [IncentivePaymentReport, BeneficiaryPaymentReport]:
        snapshot = save_report(report)
        msg = "Saving {0} to doc {1}".format(report.__name__, snapshot._id)
        logging.info(msg)
