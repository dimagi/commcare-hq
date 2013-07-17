from datetime import timedelta
from corehq.fluff.calculators.logic import ANDCalculator, ORCalculator
import fluff

def default_date(form):
    return form.received_on

# operators
EQUAL = lambda expected, reference: expected == reference
NOT_EQUAL = lambda expected, reference: expected != reference
IN = lambda expected, reference_list: expected in reference_list

class FilteredFormPropertyCalculator(fluff.Calculator):
    """
    Enables filtering forms by xmlns and (optionally) property == value.
    Let's you easily define indicators such as:
     - all adult registration forms
     - all child registration forms with foo.bar == baz
     - all newborn followups with bippity != bop

    By default just emits a single "total" value for anything matching the filter,
    though additional fields can be added by subclassing.

    These can also be chained using logic operators for fun and profit.
    """

    xmlns = None
    property_path = None
    property_value = None
    window = timedelta(days=1)

    @fluff.date_emitter
    def total(self, form):
        yield default_date(form)

    def __init__(self, xmlns=None, property_path=None, property_value=None,
                 operator=EQUAL, window=None):
        def _conditional_setattr(key, value):
            if value:
                setattr(self, key, value)

        _conditional_setattr('xmlns', xmlns)
        assert self.xmlns is not None

        _conditional_setattr('property_path', property_path)
        _conditional_setattr('property_value', property_value)
        self.operator = operator
        if self.property_path is not None:
            assert self.property_value is not None

        super(FilteredFormPropertyCalculator, self).__init__(window)

    def filter(self, form):
        # filter
        return (
            form.xmlns == self.xmlns and (
                self.property_path is None or
                self.operator(form.xpath(self.property_path), self.property_value)
            )
        )

# meh this is a little redundant but conveneient
class FormANDCalculator(ANDCalculator):
    window = timedelta(days=1)

    @fluff.date_emitter
    def total(self, form):
        yield default_date(form)

class FormORCalculator(ORCalculator):
    window = timedelta(days=1)

    @fluff.date_emitter
    def total(self, form):
        yield default_date(form)
