"""
Field definitions for the Incentive Payment Report.
Takes a CommCareUser and points to the appropriate fluff indicators
for each field.
"""

from ..opm_tasks.models import OpmReportSnapshot
from .constants import *

class Worker(object):
    method_map = [
        # If you need to change any of these names, keep the key intact
        ('name', "List of AWWs"),
        ('awc_name', "AWC Name"),
        ('bank_name', "AWW Bank Name"),
        ('account_number', "AWW Bank Account Number"),
        ('block', "Block Name"),
        ('women_registered', "No. of women registered under BCSP"),
        ('children_registered', "No. of children registered under BCSP"),
        ('service_forms_count', "Service Availability Form Submitted"),
        ('growth_monitoring_count', "No. of Growth monitoring Sections Filled for eligible children"),
        ('service_forms_cash', "Payment for Service Availability Form (in Rs.)"),
        ('growth_monitoring_cash', "Payment for Growth Monitoring Forms (in Rs.)"),
        ('month_total', "Total Payment Made for the month (in Rs.)"),
        ('last_month_total', "Amount of AWW incentive paid last month"),
    ]

    def __init__(self, worker, report, case_sql_data=None, form_sql_data=None):

        # make sure worker passes the filters
        report.filter(
            lambda key: worker.user_data.get(key),
            # user.awc, user.block
            [('awc', 'awcs'), ('block', 'blocks')]
        )

        def user_data(property):
            return worker.user_data.get(property)

        self.name = worker.name
        self.awc_name = user_data('awc')
        self.bank_name = user_data('bank_name')
        self.account_number = user_data('account_number')
        self.block = user_data('block')

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

