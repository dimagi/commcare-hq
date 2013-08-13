import fluff

class AllPregnancies(fluff.Calculator):

    @fluff.null_emitter
    def total(self, case):
        if case.type == 'pregnancy':
            yield None
