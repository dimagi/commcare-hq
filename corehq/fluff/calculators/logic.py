import warnings
import fluff


class ORCalculator(fluff.Calculator):
    """
    Lets you construct OR operations on filters.
    """
    def __init__(self, calculators):
        warnings.warn("ORCalculator is deprecated. Use ORFilter", DeprecationWarning)
        self.calculators = calculators
        assert len(self.calculators) > 1

    def filter(self, item):
        return any(calc.filter(item) for calc in self.calculators)
