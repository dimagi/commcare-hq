from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import CustomProjectReport, DatespanMixin
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, DataTablesColumnGroup
from corehq.apps.reports.filters.select import MonthFilter, YearFilter
from corehq.apps.users.models import CommCareUser, CommCareCase
from dimagi.utils.couch.database import get_db

from .beneficiary import Beneficiary
from .incentive import Worker
from .constants import DOMAIN

# logic here that pulls stuff from fluff
class BaseReport(GenericTabularReport, CustomProjectReport, DatespanMixin):
    """
    Report parent class.  Children must provide a get_rows() method that
    returns a list of the raw data that forms the basis of each row.
    The "model" attribute is an object that can accept raw_data for a row
    and perform the neccessary calculations.
    """
    name = None
    slug = None
    model = None
    fields = None

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
        # print ([self.datespan.startdate_param_utc],
        #     [self.datespan.enddate_param_utc])
        # startdate_utc is a datetime object
        rows = []
        for row in self.row_iterable:
            rows.append([getattr(row, method) for 
                method, header in self.model.method_map])
        return rows

    @property
    def row_iterable(self):
        return [self.model(row) for row in self.get_rows()]


class BeneficiaryPaymentReport(BaseReport):
    name = "Beneficiary Payment Report"
    slug = 'beneficiary_payment_report'
    model = Beneficiary
    fields = [MonthFilter, YearFilter]

    def get_rows(self):
        return CommCareCase.get_all_cases(DOMAIN, include_docs=True)


class IncentivePaymentReport(BaseReport):
    name = "Incentive Payment Report"
    slug = 'incentive_payment_report'
    model = Worker
    fields = [MonthFilter, YearFilter]
    
    def get_rows(self):
        return CommCareUser.by_domain(DOMAIN)