from dimagi.ext.jsonobject import JsonObject, StringProperty, ListProperty, BooleanProperty, DictProperty
from jsonobject import DefaultProperty
from jsonobject.exceptions import BadValueError
from corehq.apps.userreports.expressions.getters import TransformedGetter, getter_from_property_reference, \
    transform_from_datatype
from corehq.apps.userreports.operators import in_multiselect, equal
from corehq.apps.userreports.specs import TypeProperty
from corehq.apps.userreports.transforms.factory import TransformFactory


DATA_TYPE_CHOICES = ['date', 'datetime', 'string', 'integer', 'decimal']


def DataTypeProperty(**kwargs):
    """
    Shortcut for valid data types.
    """
    return StringProperty(choices=DATA_TYPE_CHOICES, **kwargs)


class IndicatorSpecBase(JsonObject):
    """
    Base class for indicator specs. All specs (for now) are assumed to have a column_id and
    a display_name, which defaults to the column_id.
    """
    _allow_dynamic_properties = False

    type = StringProperty(required=True)

    column_id = StringProperty(required=True)
    display_name = StringProperty()

    @classmethod
    def wrap(cls, obj):
        wrapped = super(IndicatorSpecBase, cls).wrap(obj)
        if not wrapped.column_id:
            raise BadValueError('column_id must not be empty!')
        if not wrapped.display_name not in obj:
            wrapped.display_name = wrapped.column_id
        return wrapped


class PropertyReferenceIndicatorSpecBase(IndicatorSpecBase):
    """
    Extension of an indicator spec that references a property - either via
    a property_name or property_path.
    """
    property_name = StringProperty()
    property_path = ListProperty()

    @property
    def getter(self):
        return getter_from_property_reference(self)


class BooleanIndicatorSpec(IndicatorSpecBase):
    type = TypeProperty('boolean')
    filter = DictProperty(required=True)


class RawIndicatorSpec(PropertyReferenceIndicatorSpecBase):
    type = TypeProperty('raw')
    datatype = DataTypeProperty(required=True)
    is_nullable = BooleanProperty(default=True)
    is_primary_key = BooleanProperty(default=False)

    @property
    def getter(self):
        transform = transform_from_datatype(self.datatype)
        getter = getter_from_property_reference(self)
        return TransformedGetter(getter, transform)


class ExpressionIndicatorSpec(IndicatorSpecBase):
    type = TypeProperty('expression')
    datatype = DataTypeProperty(required=True)
    is_nullable = BooleanProperty(default=True)
    is_primary_key = BooleanProperty(default=False)
    expression = DefaultProperty(required=True)
    transform = DictProperty(required=False)

    def parsed_expression(self, context):
        from corehq.apps.userreports.expressions.factory import ExpressionFactory
        expression = ExpressionFactory.from_spec(self.expression, context)
        datatype_transform = transform_from_datatype(self.datatype)
        if self.transform:
            generic_transform = TransformFactory.get_transform(self.transform).get_transform_function()
            inner_getter = TransformedGetter(expression, generic_transform)
        else:
            inner_getter = expression
        return TransformedGetter(inner_getter, datatype_transform)


class ChoiceListIndicatorSpec(PropertyReferenceIndicatorSpecBase):
    type = TypeProperty('choice_list')
    choices = ListProperty(required=True)
    select_style = StringProperty(choices=['single', 'multiple'])

    def get_operator(self):
        return in_multiselect if self.select_style == 'multiple' else equal


class LedgerBalancesIndicatorSpec(IndicatorSpecBase):
    type = TypeProperty('ledger_balances')
    product_codes = ListProperty(required=True)
    ledger_section = StringProperty(required=True)
    case_id_expression = DictProperty(required=True)

    def get_case_id_expression(self):
        from corehq.apps.userreports.expressions.factory import ExpressionFactory
        return ExpressionFactory.from_spec(self.case_id_expression)
