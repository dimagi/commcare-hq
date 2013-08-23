import fluff
import datetime

class custom_emitter(fluff.base_emitter):
    fluff_emitter = 'whatever'

emitter = custom_emitter()

class AllPregnancies(fluff.Calculator):
    window = datetime.timedelta(days=30)

    @fluff.null_emitter
    def total(self, case):
        if case.type == 'pregnancy':
            yield None

    # @emitter
    # def data(self, case):
    #     if case.type == 'pregnancy':
    #         yield case.name

# class FormSubmissions(fluff.Caclulator):

#     @fluff.date_emitter
#     def total(self, form):
#         if form.xmlns == 'blah':
#             yield form.received_on