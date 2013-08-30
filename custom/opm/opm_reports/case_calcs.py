import datetime

from corehq.apps.users.models import CommCareUser, CommCareCase
import fluff

from .constants import *


def case_date_group(form):
    return { 
        'date': form.received_on,
        'value': 1,
        'group_by': [
            form.domain,
            form.form['case']['@case_id'],
        ],
    }

class BirthPreparedness(fluff.Calculator):

    def __init__(self, window_attrs, *args, **kwargs):
        self.window_attrs = window_attrs
        super(BirthPreparedness, self).__init__(*args, **kwargs)

    @fluff.date_emitter
    def total(self, form):
        if form.xmlns == BIRTH_PREP_XMLNS:
            for window in self.window_attrs:
                if form.form.get(window) == '1':
                    # yield form.received_on
                    yield case_date_group(form)


class Delivery(fluff.Calculator):

    @fluff.date_emitter
    def total(self, form):
        if form.xmlns == DELIVERY_XMLNS:
            if form.form.get('mother_preg_outcome') in ['2', '3']:
                yield case_date_group(form)


def account_number_from_form(form):
    case_id = form.form['case']['@case_id']
    case = CommCareCase.get(case_id)
    return case.get_case_property("bank_account_number")


# This index is grouped by account number to be sure that it is correct
# across old cases that pertained to the same mother.
# note that get_result is overridden as well
class ChildSpacing(fluff.Calculator):

    def in_range(self, date):
        return self.start < date < self.end

    def get_cash_amt(self, dates):
        if not dates:
            return 0
        latest = sorted(dates).pop()
        two_year = latest + datetime.timedelta(365*2)
        three_year = latest + datetime.timedelta(365*3)
        if self.in_range(two_year):
            return FIXTURES['two_year_cash']
        elif self.in_range(three_year):
            return FIXTURES['three_year_cash']
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
            
