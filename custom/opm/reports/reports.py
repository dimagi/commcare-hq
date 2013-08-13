from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import CustomProjectReport, DatespanMixin
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, DataTablesColumnGroup
from corehq.apps.users.models import CommCareUser

from dimagi.utils.couch.database import get_db
from casexml.apps.case.models import CommCareCase

from .models import OPMFluff
from .case import CaseReport
from .worker import WorkerReport

# ask Biyeun about filter widgets

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
    name = None
    slug = None
    columns = None

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
            DataTablesColumn(col[0]) for col in self.columns
        ])


class BeneficiaryPaymentReport(BaseReport):
    name = "Beneficiary Payment Report"
    slug = 'beneficiary_payment_report'
    # fields = (DatespanMixin.datespan_field)
    columns = beneficiary_payment

    @property
    def cases(self):
        # filter cases, probably...
        return CommCareCase.view(
            'hqcase/by_owner',
            include_docs=True,
            reduce=False
        ).all()

    @property
    def rows(self):
        # cases = filtered_cases()
        # rows = []
        # for case in cases:
        #     rows.append([
        #         case.name,
        #         OPMFluff.get_result('all_pregnancies', [self.domain, self.user_id])['total']
        #     ])
        # return rows
        rows = []
        for case in self.cases:
            case_report = CaseReport(case)
            rows.append([getattr(case_report, col[1]) for col in self.columns])
        return rows


class IncentivePaymentReport(BaseReport):
    name = "Incentive Payment Report"
    slug = 'incentive_payment_report'
    columns = incentive_payment

    @property
    def rows(self):
        rows = []
        for worker in CommCareUser.by_domain(domain):
            worker_report = WorkerReport(worker)
            rows.append([getattr(worker_report, col[1]) for col in self.columns])
        return rows
