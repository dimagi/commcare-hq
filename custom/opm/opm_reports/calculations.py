import fluff
import datetime

from .beneficiary import Beneficiary
from .constants import *


class AllPregnancies(fluff.Calculator):
    window = datetime.timedelta(days=30)

    @fluff.null_emitter
    def total(self, case):
        if case.type == 'pregnancy':
            yield None

class BirthPreparedness(fluff.Calculator):
    window = datetime.timedelta(days=365*2)

    @fluff.date_emitter
    def total(self, case):
        for form in case.get_forms():
            # if form.xmlns == BIRTH_PREP_XMLNS:
                # for window in ['window_1_1', 'window_1_2', 'window_1_3']:
                #     if form.form.get(window) == '1':
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