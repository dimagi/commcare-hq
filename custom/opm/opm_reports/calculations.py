import fluff

class AllPregnancies(fluff.Calculator):

    @fluff.null_emitter
    def total(self, case):
        if case.type == 'pregnancy':
            yield None


# class FormSubmissions(fluff.Caclulator):

#     @fluff.date_emitter
#     def total(self, form):
#         if form.xmlns == 'blah':
#             yield form.received_on