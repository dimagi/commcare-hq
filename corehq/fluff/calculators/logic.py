import fluff

class ANDCalculator(fluff.Calculator):
    """
    WARNING: This class is deprecated. Use ANDFilter

    Lets you construct AND operations on filters.
    """
    # TODO: should we have these actually aggregate the data of the underlying
    # calculators? probably, but currently deemed out of scope

    def __init__(self, calculators):
        self.calculators = calculators
        assert len(self.calculators) > 1

    def filter(self, item):
        return all(calc.filter(item) for calc in self.calculators)

class ORCalculator(fluff.Calculator):
    """
    WARNING: This class is deprecated. Use ORFilter

    Lets you construct OR operations on filters.
    """
    def __init__(self, calculators):
        self.calculators = calculators
        assert len(self.calculators) > 1

    def filter(self, item):
        return any(calc.filter(item) for calc in self.calculators)
