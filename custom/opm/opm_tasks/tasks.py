"""
Celery tasks to save a snapshot of the reports each month
"""
import datetime
from celery import task
from django.http import HttpRequest

from dimagi.utils.dates import DateSpan
from dimagi.utils.couch.database import get_db

from ..opm_reports.reports import (BeneficiaryPaymentReport,
    IncentivePaymentReport, get_report)
from ..opm_reports.constants import DOMAIN
from .models import OpmReportSnapshot


def save_report(ReportClass, month=None, year=None):
    """
    Save a snapshot of the report.
    Pass a month and year to save an arbitrary month.
    """
    existing = OpmReportSnapshot.by_month(month, year, ReportClass.__name__)
    assert existing is None, \
        "Existing report found for %d/%d at %s" % (month, year, existing._id)
    report = get_report(ReportClass, month, year)
    snapshot = OpmReportSnapshot(
        domain=DOMAIN,
        month=month,
        year=year,
        report_class=ReportClass.__name__,
        headers=report.headers,
        slugs=report.slugs,
        rows=report.rows,
    )
    snapshot.save()


@task()
def snapshot():
    save_report(IncentivePaymentReport)
    save_report(BeneficiaryPaymentReport)
