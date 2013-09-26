"""
Fluff calculators that pertain to specific cases/beneficiaries (mothers)
These are used in the Incentive Payment Report
"""
from datetime import datetime, date, timedelta

from couchdbkit.exceptions import ResourceNotFound
from corehq.apps.fixtures.models import FixtureDataItem

from .constants import *
from .models import OpmCaseFluff, OpmUserFluff, OpmFormFluff


class Beneficiary(object):
    """
    Constructor object for each row in the Beneficiary Payment Report
    """

    # maps method name to header
    method_map = [
        # If you need to change any of these names, keep the key intact
        ('name', "List of Beneficiaries"),
        ('awc_name', "AWC Name"),
        ('bank_name', "Bank Name"),
        ('account_number', "Bank Account Number"),
        # double check this variable name
        ('ifsc_code', "IFC Code"),
        ('block', "Block Name"),
        ('village', "Village Name"),
        ('bp1_cash', "Birth Preparedness Form 1"),
        ('bp2_cash', "Birth Preparedness Form 2"),
        ('delivery_cash', "Delivery Form"),
        ('child_cash', "Child Followup Form"),
        ('spacing_cash', "Birth Spacing Bonus"),
        ('total', "Amount to be paid to beneficiary"),
    ]

    def __init__(self, case, report):
        # check filters
        for key, field in [('awc_name', 'awcs'), ('block_name', 'blocks')]:
            keys = report.filter_data.get(field, [])
            if keys and case.get_case_property(key) not in keys:
                raise InvalidRow

        try:
            self.fluff_doc = OpmCaseFluff.get("%s-%s" %
                (OpmCaseFluff._doc_type, case._id))
        except ResourceNotFound:
            raise InvalidRow
        self.name = self.fluff_doc.name
        self.awc_name = self.fluff_doc.awc_name
        self.bank_name = self.fluff_doc.bank_name
        self.account_number = self.fluff_doc.account_number
        self.ifsc_code = self.fluff_doc.ifsc_code
        self.block = self.fluff_doc.block
        self.village = self.fluff_doc.village

        def get_result(calculator):
            return OpmFormFluff.get_result(
                calculator,
                [DOMAIN, case._id],
                report.date_range,
            )['total']

        FIXTURES = get_fixture_data() 
        self.bp1_cash = get_result('bp1_cash') * FIXTURES['window_completed']
        self.bp2_cash = get_result('bp2_cash') * FIXTURES['window_completed']
        self.delivery_cash = get_result('delivery') * FIXTURES['delivery_lump_sums']
        self.child_cash = get_result('child_followup') * FIXTURES['window_completed']
        self.spacing_cash = OpmFormFluff.get_result('child_spacing',
            [DOMAIN, self.account_number], date_range=report.date_range)
        self.total = sum([self.bp1_cash, self.bp2_cash,
            self.delivery_cash, self.child_cash, self.spacing_cash])
