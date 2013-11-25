"""
Field definitions for the Incentive Payment Report.
Takes a CommCareUser and points to the appropriate fluff indicators
for each field.
"""
import datetime

from couchdbkit.exceptions import ResourceNotFound

from ..opm_tasks.models import OpmReportSnapshot
from .constants import *
from .models import OpmCaseFluff, OpmUserFluff, OpmFormFluff

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

    def __init__(self, worker, report):

        # make sure worker passes the filters
        report.filter(
            lambda key: worker.user_data.get(key),
            # user.awc, user.block
            [('awc', 'awcs'), ('block', 'blocks')]
        )

        try:
            self.fluff_doc = OpmUserFluff.get("%s-%s" %
                (OpmUserFluff._doc_type, worker._id))
        except ResourceNotFound:
            raise InvalidRow

        def fluff_attr(attr):
            return getattr(self.fluff_doc, attr, '')

        self.name = fluff_attr('name')
        self.awc_name = fluff_attr('awc_name')
        self.bank_name = fluff_attr('bank_name')
        self.account_number = fluff_attr('account_number')
        self.block = fluff_attr('block')

        def get_result(calculator, reduce=True):
            return OpmFormFluff.get_result(
                calculator,
                [DOMAIN, worker._id],
                report.date_range,
                reduce=reduce,
            )['total']

        self.women_registered = len(OpmCaseFluff.get_result(
            'women_registered',
            [DOMAIN, worker._id],
            report.date_range,
            reduce=False,
        )['total'])
        self.children_registered = OpmCaseFluff.get_result(
            'women_registered',
            [DOMAIN, worker._id],
            report.date_range,
        )['total']
        self.service_forms_count = 'yes' if get_result('service_forms') else 'no'

        self.growth_monitoring_count = get_result('growth_monitoring')

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

