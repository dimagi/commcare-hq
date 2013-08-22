from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import CustomProjectReport, DatespanMixin
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, DataTablesColumnGroup
from corehq.apps.users.models import CommCareUser, CommCareCase
from dimagi.utils.couch.database import get_db

from .models import OPMFluff
from .beneficiary import Beneficiary
from .incentive import Worker


beneficiary_payment = [
    ("List of Beneficiaries", 'name'),
    ("AWC Name", 'awc_name'),
    ("Bank Name", 'bank_name'),
    ("Bank Account Number", 'account_number'),
    ("Block Name", 'block'),
    ("Village Name", 'village'),
    ("Birth Preparedness Form 1", 'bp1_cash'),
    ("Birth Preparedness Form 2", 'bp2_cash'),
    ("Delivery Form", 'delivery_cash'),
    ("Child Followup Form", 'child_cash'),
    ("Birth Spacing Bonus", 'spacing_cash'),
    ("Amount to be paid to beneficiary", 'total'),
]

incentive_payment = [
    ("List of AWWs", 'name'),
    ("AWC Name", 'awc_name'),
    ("AWW Bank Name", 'bank_name'),
    ("AWW Bank Account Number", 'account_number'),
    ("Block Name", 'block'),
    ("No. of women registered under BCSP", 'women_registered'),
    ("No. of children registered under BCSP", 'children_registered'),
    ("Submission of Service Availability form", 'service_forms_count'),
    ("No. of Growth monitoring Sections Filled for eligible children", 'growth_monitoring_count'),
    ("Payment for Service Availability Form (in Rs.)", 'service_forms_cash'),
    ("Payment for Growth Monitoring Forms (in Rs.)", 'growth_monitoring_cash'),
    ("Total Payment Made for the month (in Rs.)", 'month_total'),
    ("Amount of AWW incentive paid last month", 'last_month_total'),
]

domain = "opm"


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
        return [self.model(row) for row in self.get_rows()]


class BeneficiaryPaymentReport(BaseReport):
    name = "Beneficiary Payment Report"
    slug = 'beneficiary_payment_report'
    model = Beneficiary

    def get_rows(self):
        return CommCareCase.get_all_cases(domain, include_docs=True)


class IncentivePaymentReport(BaseReport):
    name = "Incentive Payment Report"
    slug = 'incentive_payment_report'
    model = Worker
    raw_rows = CommCareUser.by_domain(domain)
    
    def get_rows(self):
        return CommCareUser.by_domain(domain)