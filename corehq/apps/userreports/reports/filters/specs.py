from django.utils.translation import ugettext as _
from dimagi.ext.jsonobject import (
    BooleanProperty,
    JsonObject,
    ListProperty,
    StringProperty,
)
from jsonobject.base import DefaultProperty
from corehq.apps.userreports.indicators.specs import DataTypeProperty
from corehq.apps.userreports.reports.filters.values import (
    DateFilterValue, NumericFilterValue, ChoiceListFilterValue
)
from corehq.apps.userreports.specs import TypeProperty


class ReportFilter(JsonObject):
    """
    This is a spec class that is just used for validation on a ReportConfiguration object.

    These get converted to FilterSpecs (below) by the FilterFactory.
    """
    # todo: this class is silly and can likely be removed.
    type = StringProperty(required=True)
    slug = StringProperty(required=True)
    field = StringProperty(required=True)
    display = DefaultProperty()
    compare_as_string = BooleanProperty(default=False)

    def create_filter_value(self, value):
        return {
            'date': DateFilterValue,
            'numeric': NumericFilterValue,
            'choice_list': ChoiceListFilterValue,
            'dynamic_choice_list': ChoiceListFilterValue,
        }[self.type](self, value)


class FilterChoice(JsonObject):
    value = DefaultProperty()
    display = StringProperty()

    def get_display(self):
        return self.display or self.value


def _validate_filter_slug(s):
    if "-" in s:
        raise Exception(_(
            """
            Filter slugs must be legal sqlalchemy bind parameter names.
            '-' and other special character are prohibited
            """
        ))


class FilterSpec(JsonObject):
    """
    This is the spec for a report filter - a thing that should show up as a UI filter element
    in a report (like a date picker or a select list).
    """
    type = StringProperty(required=True, choices=['date', 'numeric', 'choice_list', 'dynamic_choice_list'])
    # this shows up as the ID in the filter HTML.
    slug = StringProperty(required=True, validators=_validate_filter_slug)
    field = StringProperty(required=True)  # this is the actual column that is queried
    display = DefaultProperty()
    datatype = DataTypeProperty(default='string')

    def get_display(self):
        return self.display or self.slug


class DateFilterSpec(FilterSpec):
    compare_as_string = BooleanProperty(default=False)


class ChoiceListFilterSpec(FilterSpec):
    type = TypeProperty('choice_list')
    show_all = BooleanProperty(default=True)
    datatype = DataTypeProperty(default='string')
    choices = ListProperty(FilterChoice)


class DynamicChoiceListFilterSpec(FilterSpec):
    type = TypeProperty('dynamic_choice_list')
    show_all = BooleanProperty(default=True)
    datatype = DataTypeProperty(default='string')

    @property
    def choices(self):
        return []


class NumericFilterSpec(FilterSpec):
    type = TypeProperty('numeric')
