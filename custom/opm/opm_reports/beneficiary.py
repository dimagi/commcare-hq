"""
Fluff calculators that pertain to specific cases/beneficiaries (mothers)
These are used in the Incentive Payment Report
"""
import re
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
        ('husband_name', "Husband Name"),
        ('awc_name', "AWC Name"),
        ('bank_name', "Bank Name"),
        ('bank_branch_name', "Bank Branch Name"),
        ('bank_branch_code', "Bank Branch Code"),
        ('account_number', "Bank Account Number"),
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

        # make sure beneficiary passes the filters
        report.filter(
            lambda key: case.get_case_property(key),
            # case.awc_name, case.block_name
            [('awc_name', 'awcs'), ('block_name', 'blocks')],
        )

        if case.closed and case.closed_on <= report.datespan.startdate_utc:
            raise InvalidRow

        try:
            self.fluff_doc = OpmCaseFluff.get("%s-%s" %
                (OpmCaseFluff._doc_type, case._id))
        except ResourceNotFound:
            raise InvalidRow

        def fluff_attr(attr):
            return getattr(self.fluff_doc, attr, '')

        account = fluff_attr('account_number')
        self.account_number = str(account) if account else ''
        # fake cases will have accounts beginning with 111
        if re.match(r'^111', self.account_number):
            raise InvalidRow

        self.name = fluff_attr('name')
        self.husband_name = fluff_attr('husband_name')
        self.awc_name = fluff_attr('awc_name')
        self.bank_name = fluff_attr('bank_name')
        self.bank_branch_name = fluff_attr('bank_branch_name')
        self.bank_branch_code = fluff_attr('bank_branch_code')
        self.block = fluff_attr('block')
        self.village = fluff_attr('village')

        def get_result(calculator):
            return OpmFormFluff.get_result(
                calculator,
                [DOMAIN, case._id],
                report.date_range,
            )['total']

        FIXTURES = get_fixture_data() 
        self.bp1_cash = (FIXTURES['window_completed']
                            if get_result('bp1_cash') else 0)
        self.bp2_cash = (FIXTURES['window_completed']
                            if get_result('bp2_cash') else 0)
        self.delivery_cash = get_result('delivery') * FIXTURES['delivery_lump_sums']
        self.child_cash = (FIXTURES['window_completed'] 
                            if get_result('child_followup') else 0)
        self.spacing_cash = OpmFormFluff.get_result('child_spacing',
            [DOMAIN, self.account_number], date_range=report.date_range)
        self.total = sum([self.bp1_cash, self.bp2_cash,
            self.delivery_cash, self.child_cash, self.spacing_cash])
