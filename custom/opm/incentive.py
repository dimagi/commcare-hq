"""
Field definitions for the Incentive Payment Report.
Takes a CommCareUser and points to the appropriate fluff indicators
for each field.
"""

from custom.opm.constants import get_fixture_data


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

    # remove form_data parameter when all data will correct on HQ
    def __init__(self, worker, report, case_data=None, form_data=None):

        self.name = worker.get('name')
        self.awc_name = worker.get('awc')
        self.awc_code = worker.get('awc_code')
        self.bank_name = worker.get('bank_name')
        self.ifs_code = worker.get('ifs_code')
        self.account_number = worker.get('account_number')
        self.block = worker.get('block')
        self.owner_id = worker.get('doc_id')

        if case_data:
            self.women_registered = len(case_data)
            self.children_registered = sum([c.num_children for c in case_data if not c.is_secondary])
            for opm_case in case_data:
                dates = opm_case.data_provider.get_dates_in_range(opm_case.owner_id,
                                                                  opm_case.reporting_window_start,
                                                                  opm_case.reporting_window_end)

                self.service_forms_count = 'yes' if dates else 'no'
            self.growth_monitoring_count = len([opm_case.child_growth_calculated
                                                for opm_case in case_data
                                                if opm_case.child_growth_calculated])
        else:
            self.women_registered = None
            self.children_registered = None
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

