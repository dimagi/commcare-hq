"""
Fluff calculators that pertain to specific cases/beneficiaries (mothers)
These are used in the Incentive Payment Report
"""
from decimal import Decimal
import re
from .constants import *


class Beneficiary(object):
    """
    Constructor object for each row in the Beneficiary Payment Report
    """

    # maps method name to header
    method_map = [
        # If you need to change any of these names, keep the key intact
        ('name', "List of Beneficiaries", True),
        ('husband_name', "Husband Name", True),
        ('awc_name', "AWC Name", True),
        ('bank_name', "Bank Name", True),
        ('ifs_code', "IFS Code", True),
        ('account_number', "Bank Account Number", True),
        ('block', "Block Name", True),
        ('village', "Village Name", True),
        ('bp1_cash', "Birth Preparedness Form 1", True),
        ('bp2_cash', "Birth Preparedness Form 2", True),
        ('delivery_cash', "Delivery Form", True),
        ('child_cash', "Child Followup Form", True),
        ('spacing_cash', "Birth Spacing Bonus", True),
        ('total', "Amount to be paid to beneficiary", True),
        ('owner_id', 'Owner ID', False)
    ]

    def __init__(self, case, report, sql_form_data=None):

        # make sure beneficiary passes the filters
        filter_by = []
        if hasattr(report, 'request'):
            if report.awcs:
                filter_by = [('awc_name', 'awcs')]
            elif report.gp:
                filter_by = [('owner_id', 'gp')]
            elif report.block:
                filter_by = [('block_name', 'blocks')]

        report.filter(
            lambda key: case.get_case_property(key),
            # case.awc_name, case.block_name
            # need to be hardcoded because in case we have block_name not block property
            filter_by,
        )

        if case.closed and case.closed_on <= report.datespan.startdate_utc:
            raise InvalidRow

        def case_data(property):
            return case.get_case_property(property)

        account = case_data('bank_account_number')
        if isinstance(account, Decimal):
            account = int(account)
        self.account_number = unicode(account) if account else ''
        # fake cases will have accounts beginning with 111
        if re.match(r'^111', self.account_number):
            raise InvalidRow

        self.name = case_data('name')
        self.husband_name = case_data('husband_name')
        self.awc_name = case_data('awc_name')
        self.bank_name = case_data('bank_name')
        self.ifs_code = case_data('ifsc')
        self.block = case_data('block_name')
        self.village = case_data('village_name')
        self.owner_id = case_data('owner_id')

        def get_sql_property(property):
            property = int(0 if sql_form_data.get(property) is None
                    else sql_form_data.get(property))
            return property

        if sql_form_data:
            FIXTURES = get_fixture_data()
            self.bp1_cash = (FIXTURES['window_completed']
                                if get_sql_property('bp1_cash_total') else 0)
            self.bp2_cash = (FIXTURES['window_completed']
                                if get_sql_property('bp2_cash_total') else 0)
            self.delivery_cash = get_sql_property('delivery_total') * FIXTURES['delivery_lump_sums']
            self.child_cash = (FIXTURES['window_completed']
                                if get_sql_property('child_followup_total') else 0)
            self.spacing_cash = get_sql_property('child_spacing_deliveries')

            self.total = sum([self.bp1_cash, self.bp2_cash,
                self.delivery_cash, self.child_cash, self.spacing_cash])
        else:
            self.bp1_cash = None
            self.bp2_cash = None
            self.delivery_cash = None
            self.child_cash = None
            self.spacing_cash = None
            self.total = None
