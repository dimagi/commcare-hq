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
        ('service_forms_count', "Submission of Service Availability form"),
        ('growth_monitoring_count', "No. of Growth monitoring Sections Filled for eligible children"),
        ('service_forms_cash', "Payment for Service Availability Form (in Rs.)"),
        ('growth_monitoring_cash', "Payment for Growth Monitoring Forms (in Rs.)"),
        ('month_total', "Total Payment Made for the month (in Rs.)"),
        ('last_month_total', "Amount of AWW incentive paid last month"),
    ]

    def __init__(self, worker, date_range, last_month_totals):
        try:
            self.fluff_doc = OpmUserFluff.get("%s-%s" %
                (OpmUserFluff._doc_type, worker._id))
        except ResourceNotFound:
            print "Couldn't find fluff doc"
            raise ResourceNotFound
        self.date_range = date_range
        self.name = self.fluff_doc.name
        self.awc_name = self.fluff_doc.awc_name
        self.bank_name = self.fluff_doc.bank_name
        self.account_number = self.fluff_doc.account_number
        self.block = self.fluff_doc.block

        def get_result(calculator):
            return OpmFormFluff.get_result(
                calculator,
                [DOMAIN, worker._id],
                date_range,
            )['total']

        self.women_registered = len(OpmCaseFluff.get_result(
            'women_registered',
            [DOMAIN, worker._id],
            date_range,
            reduce=False,
        )['total'])
        self.children_registered = OpmCaseFluff.get_result(
            'women_registered',
            [DOMAIN, worker._id],
            date_range,
        )['total']
        self.service_forms_count = get_result('service_forms')
        self.growth_monitoring_count = get_result('growth_monitoring')

        self.service_forms_cash = self.service_forms_count * FIXTURES['service_form_submitted']
        self.growth_monitoring_cash = self.growth_monitoring_count * FIXTURES['child_growth_monitored']
        self.month_total = self.service_forms_cash + self.growth_monitoring_cash
        if last_month_totals is not None:
            self.last_month_total = last_month_totals.get(self.account_number, 0)
        else:
            self.last_month_total = 0

