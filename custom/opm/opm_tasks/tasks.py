"""
Celery tasks to save a snapshot of the reports each month
"""
import logging

from celery.task import periodic_task
from celery.schedules import crontab
from django.conf import settings

from ..opm_reports.reports import (BeneficiaryPaymentReport,
    IncentivePaymentReport, MetReport, get_report, last_if_none)
from ..opm_reports.constants import DOMAIN
from .models import OpmReportSnapshot

def prepare_snapshot(month, year, ReportClass, block=None):
    existing = OpmReportSnapshot.by_month(month, year, ReportClass.__name__, block)
    assert existing is None, \
        "Existing report found for %s/%s at %s" % (month, year, existing._id)
    report = get_report(ReportClass, month, year, block)
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
    month, year = last_if_none(month, year)
    if ReportClass.__name__ == "MetReport":
        for block in ['atri', 'wazirganj']:
            snapshot = prepare_snapshot(month, year, ReportClass, block)
    else:
        snapshot = prepare_snapshot(month, year, ReportClass)
    return snapshot


@periodic_task(
    run_every=crontab(hour=10, minute=1, day_of_month=1),
    queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery')
)
def snapshot():
    for report in [IncentivePaymentReport, BeneficiaryPaymentReport, MetReport]:
        snapshot = save_report(report)
        msg = "Saving {0} to doc {1}".format(report.__name__, snapshot._id)
        logging.info(msg)
