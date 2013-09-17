"""
Custom report definitions - control display of reports.

The BaseReport is somewhat general, but it's
currently specific to monthly reports.  It would be pretty simple to make
this more general and subclass for montly reports , but I'm holding off on
that until we actually have another use case for it.
"""
import datetime

from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import CustomProjectReport, MonthYearMixin 
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, DataTablesColumnGroup
from corehq.apps.users.models import CommCareUser, CommCareCase
from dimagi.utils.couch.database import get_db
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.dates import DateSpan

from couchdbkit.exceptions import ResourceNotFound

from ..opm_tasks.models import OpmReportSnapshot
from .beneficiary import Beneficiary
from .incentive import Worker
from .constants import DOMAIN


class BaseReport(MonthYearMixin, GenericTabularReport, CustomProjectReport):
    """
    Report parent class.  Children must provide a get_rows() method that
    returns a list of the raw data that forms the basis of each row.

    The "model" attribute is an object that can accept raw_data for a row
    and perform the neccessary calculations.  It must also provide a
    method_map that is a list of (method_name, "Verbose Title") tuples
    that define the columns in the report.
    """
    name = None
    slug = None
    model = None

    @property
    @memoized
    def snapshot(self):
        start = self.datespan.startdate_utc
        return OpmReportSnapshot.by_month(start.month, start.year,
            self.__class__.__name__)

    @property
    def headers(self):
        if self.snapshot is not None:
            return DataTablesHeader(*[
                DataTablesColumn(header) for header in self.snapshot.headers
            ])
        return DataTablesHeader(*[
            DataTablesColumn(header) for method, header in self.model.method_map
        ])

    @property
    def rows(self):
        # is it worth noting whether or not the data being displayed is pulled
        # from an old snapshot?
        if self.snapshot is not None:
            return self.snapshot.rows
        rows = []
        for row in self.row_objects:
            rows.append([getattr(row, method) for 
                method, header in self.model.method_map])
        return rows

    @property
    def row_objects(self):
        """
        Returns a list of objects, each representing a row in the report
        """
        start = self.datespan.startdate_utc
        end = self.datespan.enddate_utc
        now = datetime.datetime.utcnow()
        if start.year == now.year and start.month == now.month:
            end = now
        rows = []
        for row in self.get_rows(self.datespan):
            try:
                rows.append(self.model(
                    row,
                    date_range=(start, end),
                    **self.get_model_kwargs()
                ))
            except ResourceNotFound:
                print "** Row not found! **"
                print "\t", row
                pass
        return rows

    def get_model_kwargs(self):
        """
        Override this method to provide a dict of extra kwargs to the
        row constructor
        """
        return {}


class BeneficiaryPaymentReport(BaseReport):
    name = "Beneficiary Payment Report"
    slug = 'beneficiary_payment_report'
    model = Beneficiary

    def get_rows(self, datespan):
        return CommCareCase.get_all_cases(DOMAIN)


class IncentivePaymentReport(BaseReport):
    name = "Incentive Payment Report"
    slug = 'incentive_payment_report'
    model = Worker

    @property
    @memoized
    def last_month_totals(self):
        last_month = self.datespan.startdate_utc - datetime.timedelta(days=4)
        snapshot = OpmReportSnapshot.by_month(last_month.month, last_month.year,
            "IncentivePaymentReport")
        if snapshot is not None:
            total_index = snapshot.slugs.index('month_total')
            account_index = snapshot.slugs.index('account_number')
            return dict(
                (row[account_index], row[total_index]) for row in snapshot.rows
            )

    def get_model_kwargs(self):
        return {'last_month_totals': self.last_month_totals}

    def get_rows(self, datespan):
        # return [(row, self.last_month_totals) for row in CommCareUser.by_domain(DOMAIN)]
        return CommCareUser.by_domain(DOMAIN)


def get_report(ReportClass, month=None, year=None):
    """
    Utility method to run a report for an arbitrary month without a request
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
        report_class = ReportClass
        def __init__(self, *args, **kwargs):
            self.slugs, self._headers = [list(tup) for tup in zip(*self.model.method_map)]

        @property
        def headers(self):
            return self._headers

        @property
        def datespan(self):
            return DateSpan.from_month(month, year)

    return Report()