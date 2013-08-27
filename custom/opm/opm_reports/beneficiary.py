from datetime import datetime, date, timedelta

from corehq.apps.fixtures.models import FixtureDataItem

from .constants import *
from .models import OpmCaseFluff

# clarify: 1 row per bank account?

class Beneficiary(object):
    # maps method name to header
    method_map = [
        ('name', "List of Beneficiaries"),
        ('awc_name', "AWC Name"),
        ('bank_name', "Bank Name"),
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

    def __init__(self, case, form_range=None):
        """
        form_range should be a (start, stop) tuple of datetime objects
        """
        self.fluff_doc = OpmCaseFluff.get("%s-%s" %
            (OpmCaseFluff._doc_type, case['id']))

        self.name = self.fluff_doc.name
        self.awc_name = self.fluff_doc.awc_name
        self.bank_name = self.fluff_doc.bank_name
        self.account_number = self.fluff_doc.account_number
        self.block = self.fluff_doc.block
        self.village = self.fluff_doc.village

        self.bp1_cash = "Birth Preparedness Form 1"
        self.bp2_cash = "Birth Preparedness Form 2"
        self.delivery_cash = "Delivery Form"
        self.child_cash = "Child Followup Form"
        self.spacing_cash = "Birth Spacing Bonus"
        self.total = "Amount to be paid to beneficiary"


        # self.case = case
        # self.forms = case.get_forms()
        # self.name = case.name
        # self.account_number = case.get_case_property('bank_account_number') or ""
        # if form_range:
        #     self.start = form_range[0]
        #     self.stop = form_range[1]
        # else:
        #     self.start = date.min
        #     self.stop = date.max # or should it be date.today() ?

        # # self.forms_in_range = [form for form in self.forms if
        # #     (form.received_on.date() > self.start) and (form.received_on.date() < self.stop)

        # self.forms_in_range = [form for form in self.forms if
        #     (self.start < form.received_on.date() < self.stop)]

    # @property
    # def bank_name(self):
    #     # to be converted to case property?
    #     for form in self.forms:
    #         if form.xmlns == PREG_REG_XMLNS:
    #             return form.form.get('bank_name', "")
    #     return ""

    # @property
    # def awc_name(self):
    #     # from fixture for a given case
    #     return "Anganwadi Center"

    # @property
    # def block(self):
    #     # from fixture
    #     return "Block Name"

    # @property
    # def village(self):
    #     # from fixture
    #     return "Village Name"

    # def bp_cash(self, windows, cash_fixture):
    #     for form in self.forms_in_range:
    #         if form.xmlns == BIRTH_PREP_XMLNS:
    #             for window in windows:
    #                 if form.form.get(window) == '1':
    #                     return cash_fixture
    #     return 0

    # @property
    # def bp1_cash(self):
    #     cash_fixture = 100
    #     return self.bp_cash(['window_1_1', 'window_1_2', 'window_1_3'], cash_fixture)

    # @property
    # def bp2_cash(self):
    #     cash_fixture = 200
    #     return self.bp_cash(['window_2_1', 'window_2_2', 'window_2_3'], cash_fixture)

    # @property
    # def delivery_cash(self):
    #     cash_fixture = 400
    #     for form in self.forms_in_range:
    #         if form.xmlns == DELIVERY_XMLNS:
    #             if form.form.get('mother_preg_outcome') in ['2', '3']:
    #                 return cash_fixture
    #     return 0
    
    # @property
    # def child_cash(self):
    #     cash_fixture = 300
    #     for form in self.forms_in_range:
    #         if form.xmlns == CHILD_FOLLOWUP_XMLNS:
    #             # awaiting proper data node
    #             # maybe 'child1_received_pnc' ?
    #             if form.form.get('child1_attendance_vhnd') == '1':
    #                 return cash_fixture
    #     return 0

    # @property
    # def spacing_cash(self):
    #     return 0
    #     # clarify: possibly 2 payments?  (2 yrs since birth and 3?)
    #     # clearly not...
    #     # calculate across cases by bank account number!
    #     # get "Registration Form" > 'bank_account_number'
    #     # mother = # collection of all cases with matching bank account number

    #     # cash_fixture = 75
    #     # payment1, payment 2 = 0, 0
    #     # for dod in mother.dods:
    #     #     year2 = dod + timedelta(days=365*2)
    #     #     year3 = dod + timedelta(days=365*3)
    #     #     if self.start < year2 < self.stop:
    #     #         if not mother.is_pregnant:
    #     #             payment1 = cash_fixture
    #     #     if self.start < year3 < self.stop:
    #     #         if not mother.is_pregnant:
    #     #             payment2 = cash_fixture
    #     # return payment1 + payment2 # max 1 cash_fixture each

    #     # for form in self.forms:
    #     #     if form.xmlns == DELIVERY_XMLNS:
    #     #         dod = form.form.get('dod')
    #     # return "Birth Spacing Bonus"

    # @property
    # def total(self):
    #     return (
    #         self.bp1_cash +
    #         self.bp2_cash +
    #         self.delivery_cash +
    #         self.child_cash +
    #         self.spacing_cash
    #     )
