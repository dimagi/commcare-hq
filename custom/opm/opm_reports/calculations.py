import fluff
import datetime

from .constants import *


class AllPregnancies(fluff.Calculator):
    window = datetime.timedelta(days=30)

    @fluff.null_emitter
    def total(self, case):
        if case.type == 'pregnancy':
            yield None


def get_case_id(form):
    try:
        return form.form['case']['@case_id']
    except KeyError:
        return None


def get_user_id(form):
    try:
        return form.metadata.userID
    except AttributeError:
        return None


class BirthPreparedness(fluff.Calculator):
    window = datetime.timedelta(days=365*2)

    def __init__(self, window_attrs, *args, **kwargs):
        self.window_attrs = window_attrs
        super(BirthPreparedness, self).__init__(*args, **kwargs)

    @fluff.date_emitter
    def total(self, form):
        if form.xmlns == BIRTH_PREP_XMLNS:
            for window in self.window_attrs:
                if form.form.get(window) == '1':
                    yield { 
                        'date': form.received_on,
                        'value': 1,
                        'group_by': (
                            'domain',
                            form.form['case']['@case_id'],
                        ),
                    }


class Delivery(fluff.Calculator):
    window = datetime.timedelta(days=365*2)

    @fluff.date_emitter
    def total(self, form):
        if form.xmlns == DELIVERY_XMLNS:
            # if form.form.get('mother_preg_outcome') in ['2', '3']:
            yield form.received_on


    # @emitter
    # def data(self, case):
    #     if case.type == 'pregnancy':
    #         yield case.name

# class FormSubmissions(fluff.Calculator):

#     @fluff.date_emitter
#     def total(self, form):
#         if form.xmlns == 'blah':
#             yield form.received_on