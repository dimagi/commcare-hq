"""
Custom report definitions.
"""
import datetime

from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import CustomProjectReport, MonthYearMixin 
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, DataTablesColumnGroup
from corehq.apps.users.models import CommCareUser, CommCareCase
from dimagi.utils.couch.database import get_db

from couchdbkit.exceptions import ResourceNotFound

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
    def filters(self):
        return [
            "date between :startdate and :enddate"
        ]

    @property
    def filter_values(self):
        return {
            "startdate": self.datespan.startdate_param_utc,
            "enddate": self.datespan.enddate_param_utc
        }

    @property
    def headers(self):
        return DataTablesHeader(*[
            DataTablesColumn(header) for method, header in self.model.method_map
        ])

    @property
    def rows(self):
        rows = []
        for row in self.row_iterable:
            rows.append([getattr(row, method) for 
                method, header in self.model.method_map])
        return rows

    @property
    def row_iterable(self):
        start = self.datespan.startdate_utc
        end = self.datespan.enddate_utc
        now = datetime.datetime.utcnow()
        if start.year == now.year and start.month == now.month:
            end = now

        print "*"*20
        print start
        print end

        rows = []
        for row in self.get_rows():
            try:
                rows.append(self.model(row, date_range=(start, end)))
            except ResourceNotFound:
                pass
        return rows


class BeneficiaryPaymentReport(BaseReport):
    name = "Beneficiary Payment Report"
    slug = 'beneficiary_payment_report'
    model = Beneficiary

    def get_rows(self):
        return CommCareCase.get_all_cases(DOMAIN)


class IncentivePaymentReport(BaseReport):
    name = "Incentive Payment Report"
    slug = 'incentive_payment_report'
    model = Worker
    
    def get_rows(self):
        return CommCareUser.by_domain(DOMAIN)
