"""
Celery tasks to save a snapshot of the reports each month
"""
import datetime
from celery import task
from django.http import HttpRequest
from couchdbkit.exceptions import ResourceNotFound

from dimagi.utils.dates import DateSpan
from dimagi.utils.couch.database import get_db

from ..opm_reports.reports import BeneficiaryPaymentReport, IncentivePaymentReport
from ..opm_reports.constants import DOMAIN
from .models import OpmReportSnapshot


def save_report(ReportClass, month=None, year=None):
    """
    Save a snapshot of the report.
    Pass a month and year to save an arbitrary month.
    """
    if month is not None:
        assert year is not None, \
            "You must pass either nothing or a month AND a year"
    else:
        last_month = datetime.datetime.now() - datetime.timedelta(days=4)
        month = last_month.month
        year = last_month.year

    class Report(ReportClass):
        snapshot = None
        def __init__(self, *args, **kwargs):
            pass

        @property
        def headers(self):
            self.slugs, headers = [list(tup) for tup in zip(*self.model.method_map)]
            return headers

        @property
        def datespan(self):
            return DateSpan.from_month(month, year)

    existing = OpmReportSnapshot.by_month(month, year, ReportClass.__name__)
    assert existing is None, \
        "Existing report found for %d/%d at %s" % (month, year, existing._id)

    report = Report()
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
