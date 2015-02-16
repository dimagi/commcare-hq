from jsonobject import JsonObject, StringProperty, ListProperty, BooleanProperty, DictProperty
from jsonobject.exceptions import BadValueError
from corehq.apps.userreports.expressions.factory import ExpressionFactory
from corehq.apps.userreports.expressions.getters import TransformedGetter, getter_from_property_reference, \
    transform_date, transform_int
from corehq.apps.userreports.operators import IN_MULTISELECT, EQUAL
from corehq.apps.userreports.specs import TypeProperty


def DataTypeProperty():
    """
    Shortcut for valid data types.
    """
    return StringProperty(required=True, choices=['date', 'datetime', 'string', 'integer', 'decimal'])


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
    datatype = DataTypeProperty()
    is_nullable = BooleanProperty(default=True)
    is_primary_key = BooleanProperty(default=False)

    @property
    def getter(self):
        transform = _transform_from_datatype(self.datatype)
        getter = getter_from_property_reference(self)
        return TransformedGetter(getter, transform)


class ExpressionIndicatorSpec(IndicatorSpecBase):
    type = TypeProperty('expression')
    datatype = DataTypeProperty()
    is_nullable = BooleanProperty(default=True)
    is_primary_key = BooleanProperty(default=False)
    expression = DictProperty(required=True)

    def parsed_expression(self, context):
        transform = _transform_from_datatype(self.datatype)
        expression = ExpressionFactory.from_spec(self.expression, context)
        return TransformedGetter(expression, transform)


class ChoiceListIndicatorSpec(PropertyReferenceIndicatorSpecBase):
    type = TypeProperty('choice_list')
    choices = ListProperty(required=True)
    select_style = StringProperty(choices=['single', 'multiple'])

    def get_operator(self):
        return IN_MULTISELECT if self.select_style == 'multiple' else EQUAL


def _transform_from_datatype(datatype):
    return {
        'date': transform_date,
        'integer': transform_int,
    }.get(datatype)
