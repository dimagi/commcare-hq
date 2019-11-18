from corehq.fluff.calculators.xform import ANY, EQUAL
from fluff.filters import Filter


class CasePropertyFilter(Filter):
    """
    Enables filtering cases by type and (optionally) property == value.
    """

    type = None
    property_name = None
    property_value = None

    def __init__(self, type=None, property_name=None, property_value=None, operator=EQUAL):
        def _conditional_setattr(key, value):
            if value:
                setattr(self, key, value)

        _conditional_setattr('type', type)
        assert self.type is not None

        _conditional_setattr('property_name', property_name)
        _conditional_setattr('property_value', property_value)
        if self.property_name is not None and operator != ANY:
            assert self.property_value is not None

        self.operator = operator

    def filter(self, case):
        return (
            case.type == self.type and (
                self.property_name is None or
                self.operator(case.get_case_property(self.property_name), self.property_value)
            )
        )
