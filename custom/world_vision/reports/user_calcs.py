import fluff

class MotherRegistered(fluff.Calculator):
    @fluff.date_emitter
    def total(self, case):
        yield case.opened_on