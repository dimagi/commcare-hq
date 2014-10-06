"""
Field definitions for the Incentive Payment Report.
Takes a CommCareUser and points to the appropriate fluff indicators
for each field.
"""

from .constants import *

class Worker(object):
    method_map = [
        # If you need to change any of these names, keep the key intact
        ('name', "List of AWWs", True),
        ('awc_name', "AWC Name", True),
        ('awc_code', "AWC Code", True),
        ('bank_name', "AWW Bank Name", True),
        ('ifs_code', "IFS Code", True),
        ('account_number', "AWW Bank Account Number", True),
        ('block', "Block Name", True),
        ('women_registered', "No. of women registered under BCSP", True),
        ('children_registered', "No. of children registered under BCSP", True),
        ('service_forms_count', "Service Availability Form Submitted", True),
        ('growth_monitoring_count', "No. of Growth monitoring Sections Filled for eligible children", True),
        ('service_forms_cash', "Payment for Service Availability Form (in Rs.)", True),
        ('growth_monitoring_cash', "Payment for Growth Monitoring Forms (in Rs.)", True),
        ('month_total', "Total Payment Made for the month (in Rs.)", True),
        ('last_month_total', "Amount of AWW incentive paid last month", True),
        ('owner_id', 'Owner ID', False)
    ]

    def __init__(self, worker, report, case_sql_data=None, form_sql_data=None):

        self.name = worker.get('name')
        self.awc_name = worker.get('awc')
        self.awc_code = worker.get('awc_code')
        self.bank_name = worker.get('bank_name')
        self.ifs_code = worker.get('ifs_code')
        self.account_number = worker.get('account_number')
        self.block = worker.get('block')
        self.owner_id = worker.get('doc_id')

        if case_sql_data:
            self.women_registered = str(case_sql_data.get('women_registered_total', None))
            self.children_registered = str(case_sql_data.get('children_registered_total', None))
        else:
            self.women_registered = None
            self.children_registered = None

        if form_sql_data:
            self.service_forms_count = 'yes' if form_sql_data.get('service_forms_total') else 'no'
            self.growth_monitoring_count = int(0 if form_sql_data.get('growth_monitoring_total') is None else form_sql_data.get('growth_monitoring_total'))
        else:
            self.service_forms_count = 'no'
            self.growth_monitoring_count = 0

        FIXTURES = get_fixture_data()
        self.service_forms_cash = FIXTURES['service_form_submitted'] \
                if self.service_forms_count == 'yes' else 0
        self.growth_monitoring_cash = self.growth_monitoring_count * FIXTURES['child_growth_monitored']
        self.month_total = self.service_forms_cash + self.growth_monitoring_cash
        if report.last_month_totals is not None:
            self.last_month_total = report.last_month_totals.get(
                self.account_number, 0)
        else:
            self.last_month_total = 0

