"""
Fluff calculators that pertain to specific cases/beneficiaries (mothers).
These are used in the Beneficiary Payment Report
"""
import datetime

from corehq.apps.users.models import CommCareUser, CommCareCase
import fluff

from .constants import *


def get_case(form):
    case_id = form.form['case']['@case_id']
    return CommCareCase.get(case_id)


def block_type(form):
    case = get_case(form)
    block = case.get_case_property('block_name')
    if block:
        if block.lower() == "atri":
            return 'hard'
        elif block.lower() == "wazirganj":
            return 'soft'


def case_date_group(form):
    return form.received_on

class BirthPreparedness(fluff.Calculator):
    """
    Birth Preparedness Form

    Within the dates the report is run, in the Birth Preparedness form,
    if either window_1_1, window_1_2, or window_1_3 = '1' . This will only
    count for the most recent form submitted within the report range. Cash
    amounts in fixture. (To be included on my end, data node referencing case
    type=vhnd to trigger on those data nodes if window_1_x = 0 AND services
    not available) These will all be based on the form. Will be filled out
    multiple times throughout pregnancy, but report should only include 1x
    (most recent) per reporting period.
    """

    def __init__(self, window_attrs, *args, **kwargs):
        self.window_attrs = window_attrs
        super(BirthPreparedness, self).__init__(*args, **kwargs)

    @fluff.date_emitter
    def total(self, form):
        if form.xmlns == BIRTH_PREP_XMLNS:
            block = block_type(form)
            for window in self.window_attrs:
                if block == 'soft' and window[-1] == '3':
                    window = "soft_%s" % window
                if form.form.get(window) == '1':
                    yield case_date_group(form)


class Delivery(fluff.Calculator):
    """
    Delivery Form

    From Delivery Form data, cash amount from fixture if
    mother_preg_outcome = "2" or "3" to also only be included within the dates
    the report is run. (These would also close the case). Cash amounts in
    fixture.
    """

    @fluff.date_emitter
    def total(self, form):
        if form.xmlns == DELIVERY_XMLNS:
            if form.form.get('mother_preg_outcome') in ['2', '3']:
                yield case_date_group(form)


def account_number_from_form(form):
    case = get_case(form)
    return case.get_case_property("bank_account_number")

       
class ChildFollowup(fluff.Calculator):
    """
    Child Followup Form

    Similar to Birth Preparedness Form, this will be calculated in the Child
    Followup form (data node not yet made) which will trigger "1" based on the
    combination of relevant conditions - only include those that trigger
    within the dates the report is run.  Only count the most recent form
    submitted within the date range. This form will be filled out monthly, so
    if filled out 10x, does not = 10x the condition amount (should be 1x per
    report period). Cash amounts will be in fixture.
    """

    @fluff.date_emitter
    def total(self, form):
        if form.xmlns == CHILD_FOLLOWUP_XMLNS:
            followed_up = False
            for prop in [
                'window%d_child%d' % (window, child)
                for window in range(3, 15) for child in range(1, 4)
            ]:
                if form.form.get(prop):# == '1':
                    followed_up = True
            if followed_up:
                yield case_date_group(form)


class ChildSpacing(fluff.Calculator):
    """
    Birth Spacing Bonus

    This will be calculated across cases for case type = pregnancy and will
    include open and closed cases. Since delivery (Delivery form, question
    id = dod), generally if no other pregnancy with the same bank account
    number (registration form, question id = bank_account_number) at the time
    the report is run or there is another match with bank account number,
    null. If 2yr since delivery (dod) is within date range of report, and this
    case does not have another case with matching bank account # for a future
    date of delivery, trigger payment. Also trigger another payment if there
    is 3yr since dod and if no other matching bank account registrations
    within the range. This should only trigger for the report which falls
    under the date range. Cash amounts will be in fixture.

    This index is grouped by account number to be sure that it is correct
    across old cases that pertained to the same mother.
    note that get_result is overridden as well
    """

    def in_range(self, date):
        return self.start.date() <= date < self.end.date()

    def get_cash_amt(self, dates):
        if not dates:
            return 0
        latest = sorted(dates).pop()
        two_year = latest + datetime.timedelta(365*2)
        three_year = latest + datetime.timedelta(365*3)
        FIXTURES = get_fixture_data()
        if self.in_range(two_year):
            return FIXTURES['two_year_spacing']
        elif self.in_range(three_year):
            return FIXTURES['three_year_spacing']
        else:
            return 0

    def get_result(self, key, date_range=None, **kwargs):
        self.start, self.end = date_range
        shared_key = [self.fluff._doc_type] + key + [self.slug, 'deliveries']
        q_args = {'reduce': False}
        query = self.fluff.view(
            'fluff/generic',
            startkey=shared_key,
            endkey=shared_key + [{}],
            **q_args
        ).all()
        def convert_date(date_str):
            return datetime.date(*[int(d) for d in date_str.split('-')])
        dates = [convert_date(delivery['key'][-1]) for delivery in query]
        return self.get_cash_amt(dates)


    @fluff.date_emitter
    def deliveries(self, form):
        if form.xmlns == DELIVERY_XMLNS:
            dod = form.form.get('dod')
            if isinstance(dod, (datetime.datetime, datetime.date)):
                yield {
                    'date': dod,
                    'value': 1,
                    'group_by': [
                        form.domain,
                        account_number_from_form(form),
                    ]
                }
