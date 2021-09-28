from django.conf import settings
from django.utils.module_loading import import_string

from jsonobject.base import DefaultProperty

from dimagi.ext.jsonobject import (
    BooleanProperty,
    DictProperty,
    IntegerProperty,
    JsonObject,
    ListProperty,
    StringProperty,
)

from corehq.apps.userreports.datatypes import DataTypeProperty
from corehq.apps.userreports.reports.filters.choice_providers import (
    DATA_SOURCE_COLUMN,
)
from corehq.apps.userreports.reports.filters.values import (
    ChoiceListFilterValue,
    DateFilterValue,
    LocationDrilldownFilterValue,
    MultiFieldChoiceListFilterValue,
    NumericFilterValue,
    PreFilterValue,
    QuarterFilterValue,
)
from corehq.apps.userreports.specs import TypeProperty


class FilterValueFactory:
    class_map = {
        'quarter': QuarterFilterValue,
        'date': DateFilterValue,
        'numeric': NumericFilterValue,
        'pre': PreFilterValue,
        'choice_list': ChoiceListFilterValue,
        'dynamic_choice_list': ChoiceListFilterValue,
        'multi_field_dynamic_choice_list': MultiFieldChoiceListFilterValue,
        'location_drilldown': LocationDrilldownFilterValue,
    }

    @classmethod
    def from_spec(cls, spec, value):
        return cls.class_map[spec['type']](spec, value)


def create_filter_value(raw_filter_spec, value):
    return FilterValueFactory.from_spec(raw_filter_spec, value)


class FilterChoice(JsonObject):
    value = DefaultProperty()
    display = StringProperty()

    def get_display(self):
        return self.display or self.value


class FilterSpec(JsonObject):
    """
    This is the spec for a report filter - a thing that should show up as a UI filter element
    in a report (like a date picker or a select list).
    """
    type = StringProperty(
        required=True,
        choices=[
            'date', 'quarter', 'numeric', 'pre', 'choice_list', 'dynamic_choice_list',
            'multi_field_dynamic_choice_list', 'location_drilldown',
            'village_choice_list'
        ]
    )
    # this shows up as the ID in the filter HTML.
    slug = StringProperty(required=True)
    field = StringProperty(required=True)  # this is the actual column that is queried
    display = DefaultProperty()
    datatype = DataTypeProperty(default='string')

    def get_display(self):
        return self.display or self.slug

    @classmethod
    def wrap(cls, *args, **kwargs):
        # Because pre_value is set to DefaultProperty, pre_value is automatically
        # interpreted to be a datatype when it's fetched by jsonobject.
        # This fails hard when the spec expects a string
        # and gets something else...like a date.
        doc = args[0]
        if 'pre_value' in doc:
            pre_value = doc['pre_value']
            data_type = doc.get('datatype')
            if data_type == 'string':
                doc['pre_value'] = str(pre_value)

        return super().wrap(*args, **kwargs)


class DateFilterSpec(FilterSpec):
    compare_as_string = BooleanProperty(default=False)


class QuarterFilterSpec(FilterSpec):
    type = TypeProperty('quarter')
    show_all = BooleanProperty(default=False)


class ChoiceListFilterSpec(FilterSpec):
    type = TypeProperty('choice_list')
    show_all = BooleanProperty(default=True)
    datatype = DataTypeProperty(default='string')
    choices = ListProperty(FilterChoice)


class DynamicChoiceListFilterSpec(FilterSpec):
    type = TypeProperty('dynamic_choice_list')
    show_all = BooleanProperty(default=True)
    datatype = DataTypeProperty(default='string')
    choice_provider = DictProperty()
    ancestor_expression = DictProperty(default={}, required=False)

    def get_choice_provider_spec(self):
        return self.choice_provider or {'type': DATA_SOURCE_COLUMN}

    @property
    def choices(self):
        return []


class MultiFieldDynamicChoiceFilterSpec(DynamicChoiceListFilterSpec):
    type = TypeProperty('multi_field_dynamic_choice_list')
    fields = ListProperty(default=[])


class LocationDrilldownFilterSpec(FilterSpec):
    type = TypeProperty('location_drilldown')
    include_descendants = BooleanProperty(default=False)
    # default to some random high number '99'
    max_drilldown_levels = IntegerProperty(default=99)
    ancestor_expression = DictProperty(default={}, required=False)


class PreFilterSpec(FilterSpec):
    type = TypeProperty('pre')
    pre_value = DefaultProperty(required=True)
    pre_operator = StringProperty(default=None, required=False)


class NumericFilterSpec(FilterSpec):
    type = TypeProperty('numeric')
