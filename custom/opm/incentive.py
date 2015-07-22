"""
Field definitions for the Incentive Payment Report.
Takes a CommCareUser and points to the appropriate fluff indicators
for each field.
"""
from collections import defaultdict
from corehq.apps.reports.datatables import DTSortType

from custom.opm.constants import get_fixture_data
from custom.opm.utils import numeric_fn


class Worker(object):
    method_map = [
        # If you need to change any of these names, keep the key intact
        ('name', "List of AWWs", True, None),
        ('awc_name', "AWC Name", True, None),
        ('awc_code', "AWC Code", True, DTSortType.NUMERIC),
        ('bank_name', "AWW Bank Name", True, None),
        ('ifs_code', "IFS Code", True, None),
        ('account_number', "AWW Bank Account Number", True, None),
        ('block', "Block Name", True, None),
        ('beneficiaries_registered', "No. of beneficiaries registered under BCSP", True, DTSortType.NUMERIC),
        ('children_registered', "No. of children registered under BCSP", True, DTSortType.NUMERIC),
        ('service_forms_count', "Service Availability Form Submitted", True, None),
        ('growth_monitoring_count', "No. of Growth monitoring Sections Filled for eligible children", True,
         DTSortType.NUMERIC),
        ('service_forms_cash', "Payment for Service Availability Form (in Rs.)", True, DTSortType.NUMERIC),
        ('growth_monitoring_cash', "Payment for Growth Monitoring Forms (in Rs.)", True, DTSortType.NUMERIC),
        ('month_total', "Total Payment Made for the month (in Rs.)", True, DTSortType.NUMERIC),
        ('last_month_total', "Amount of AWW incentive paid last month", True, DTSortType.NUMERIC),
        ('owner_id', 'Owner ID', False, None),
    ]

    # remove form_data parameter when all data will correct on HQ
    def __init__(self, worker, report, case_data=None, form_data=None):
        self.debug = report.debug
        self.case_data = case_data or []
        self.name = worker.get('name')
        self.awc_name = worker.get('awc')
        self.awc_code = numeric_fn(worker.get('awc_code'))
        self.bank_name = worker.get('bank_name')
        self.ifs_code = worker.get('ifs_code')
        self.account_number = worker.get('account_number')
        self.block = worker.get('block')
        self.owner_id = worker.get('doc_id')
        self.growth_monitoring_contributions = defaultdict(lambda: 0)
        if case_data:
            self.beneficiaries_registered = numeric_fn(len(case_data))
            self.children_registered = numeric_fn(sum([c.raw_num_children for c
                                                       in case_data if not c.is_secondary]))

            for opm_case in case_data:
                dates = opm_case.data_provider.get_dates_in_range(opm_case.owner_id,
                                                                  opm_case.reporting_window_start,
                                                                  opm_case.reporting_window_end)

                self.service_forms_count = 'yes' if dates else 'no'

            for row in self.case_data:
                if row.growth_calculated_aww:
                    self.growth_monitoring_contributions[(row.case_id, row.child_index)] += 1

            monitoring_count = len(self.growth_monitoring_contributions.keys())
        else:
            self.beneficiaries_registered = None
            self.children_registered = None
            self.service_forms_count = 'no'
            monitoring_count = 0

        self.growth_monitoring_count = numeric_fn(monitoring_count)
        FIXTURES = get_fixture_data()
        forms_cash = FIXTURES['service_form_submitted'] \
            if self.service_forms_count == 'yes' else 0
        self.service_forms_cash = numeric_fn(forms_cash)
        monitoring_cash = monitoring_count * FIXTURES['child_growth_monitored']
        self.growth_monitoring_cash = numeric_fn(monitoring_cash)
        self.month_total = numeric_fn(forms_cash + monitoring_cash)
        if report.last_month_totals is not None:
            self.last_month_total = numeric_fn(report.last_month_totals.get(
                self.account_number, 0))
        else:
            self.last_month_total = numeric_fn(0)

    @property
    def debug_info(self):
        if self.debug:
            child_registered_contributions = {
                row.case_id: row.raw_num_children for row in self.case_data
                if row.raw_num_children and not row.is_secondary
            }
            return 'Registration:<br>{}<br>Growth Monitoring:<br>{}'.format(
                '<br>'.join('{}: {}'.format(k, v) for k, v in child_registered_contributions.items()),
                '<br>'.join('{}, {}: {}'.format(k[0], k[1], v)
                            for k, v in self.growth_monitoring_contributions.items())
            )
        else:
            return ''
