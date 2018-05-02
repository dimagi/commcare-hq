from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import timedelta
import warnings
import fluff
from fluff.filters import Filter, ORFilter, ANDFilter
from fluff.models import SimpleCalculator


def default_date(form):
    return form.received_on


def in_range_calc(input, reference_tuple):
    if not input:
        # filter empty strings
        return False

    try:
        # attempt to make it an int first as it would help
        # make the comparison accurate
        value = int(input)
    except ValueError:
        value = float(input)

    return value >= reference_tuple[0] and value < reference_tuple[1]

# operators
EQUAL = lambda input, reference: input == reference
NOT_EQUAL = lambda input, reference: input != reference
IN = lambda input, reference_list: input in reference_list
IN_MULTISELECT = lambda input, reference: reference in (input or '').split(' ')
ANY = lambda input, reference: bool(input)
SKIPPED = lambda input, reference: input is None
IN_RANGE = lambda input, reference_tuple: in_range_calc(input, reference_tuple)


def ANY_IN_MULTISELECT(input, reference):
    """
    For 'this multiselect contains any one of these N items'
    """
    return any([subval in (input or '').split(' ') for subval in reference])


class IntegerPropertyReference(object):
    """
    Returns the integer value of the property_path passed in.

    By default FilteredFormPropertyCalculator would use 1 for all results
    but this will let you return the actual number to be summed.

    Accepts an optional transform lambda/method that would modify the
    resulting integer before returning it.
    """

    def __init__(self, property_path, transform=None):
        self.property_path = property_path
        self.transform = transform

    def __call__(self, form):
        value = int(form.get_data(self.property_path) or 0)
        if value and self.transform:
            value = self.transform(value)
        return value


def requires_property_value(operator):
    return not (operator == ANY or operator == SKIPPED)


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
    indicator_calculator = None
    window = timedelta(days=1)

    @fluff.date_emitter
    def total(self, form):
        if not self.indicator_calculator:
            yield default_date(form)
        else:
            yield [default_date(form), self.indicator_calculator(form)]

    def __init__(self, xmlns=None, property_path=None, property_value=None,
                 operator=EQUAL, indicator_calculator=None, window=None):
        warnings.warn("FilteredFormPropertyCalculator is deprecated. "
                      "Use SimpleCalculator in combination with FormPropertyFilter", DeprecationWarning)

        def _conditional_setattr(key, value):
            if value:
                setattr(self, key, value)

        _conditional_setattr('xmlns', xmlns)
        assert self.xmlns is not None

        _conditional_setattr('property_path', property_path)
        _conditional_setattr('property_value', property_value)

        if self.property_path is not None and requires_property_value(operator):
            assert self.property_value is not None

        self.operator = operator
        _conditional_setattr('indicator_calculator', indicator_calculator)

        super(FilteredFormPropertyCalculator, self).__init__(window)

    def filter(self, form):
        # filter
        return (
            form.xmlns == self.xmlns and (
                self.property_path is None or
                self.operator(form.get_data(self.property_path), self.property_value)
            )
        )


class FormPropertyFilter(Filter):
    """
    Enables filtering forms by xmlns and (optionally) property == value.
    Let's you easily define indicators such as:
     - all adult registration forms
     - all child registration forms with foo.bar == baz
     - all newborn followups with bippity != bop

    These can also be chained using logic operators for fun and profit.
    """

    xmlns = None
    property_path = None
    property_value = None

    def __init__(self, xmlns=None, property_path=None, property_value=None, operator=EQUAL):
        def _conditional_setattr(key, value):
            if value:
                setattr(self, key, value)

        _conditional_setattr('xmlns', xmlns)
        assert self.xmlns is not None

        _conditional_setattr('property_path', property_path)
        _conditional_setattr('property_value', property_value)

        if self.property_path is not None and requires_property_value(operator):
            assert self.property_value is not None

        self.operator = operator

    def filter(self, form):
        return (
            form.xmlns == self.xmlns and (
                self.property_path is None or
                self.operator(form.get_data(self.property_path), self.property_value)
            )
        )


class FormSUMCalculator(fluff.Calculator):
    window = timedelta(days=1)

    def __init__(self, calculators):
        self.calculators = calculators
        assert len(self.calculators) > 1

    def filter(self, item):
        return any(calc.filter(item) for calc in self.calculators)

    @fluff.date_emitter
    def total(self, form):
        for calc in self.calculators:
            if calc.passes_filter(form):
                for total in calc.total(form):
                    yield total


def filtered_form_calc(xmlns=None, property_path=None, property_value=None,
                         operator=EQUAL, date_provider=default_date,
                         indicator_calculator=None, group_by_provider=None,
                         window=timedelta(days=1)):
    """
    Shortcut function for creating a SimpleCalculator with a FormPropertyFilter
    """
    filter = FormPropertyFilter(xmlns=xmlns, property_path=property_path,
                                property_value=property_value,
                                operator=operator)

    return SimpleCalculator(
        date_provider=date_provider,
        filter=filter,
        indicator_calculator=indicator_calculator,
        group_by_provider=group_by_provider,
        window=window
    )


def or_calc(calculators, date_provider=default_date, indicator_calculator=None,
            group_by_provider=None, window=timedelta(days=1)):
    """
    Shortcut function for creating a SimpleCalculator with a filter that combines
    the filters of the calculators in an ORFilter
    """
    return SimpleCalculator(
        date_provider=date_provider,
        filter=ORFilter([calc._filter for calc in calculators if calc._filter]),
        indicator_calculator=indicator_calculator,
        group_by_provider=group_by_provider,
        window=window
    )


def and_calc(calculators, date_provider=default_date, indicator_calculator=None,
            group_by_provider=None, window=timedelta(days=1)):
    """
    Shortcut function for creating a SimpleCalculator with a filter that combines
    the filters of the calculators in an ANDFilter
    """
    return SimpleCalculator(
        date_provider=date_provider,
        filter=ANDFilter([calc._filter for calc in calculators if calc._filter]),
        indicator_calculator=indicator_calculator,
        group_by_provider=group_by_provider,
        window=window
    )
