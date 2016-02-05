import json
from couchdbkit.exceptions import ResourceNotFound
from datetime import timedelta
from corehq.apps.userreports.exceptions import BadSpecError
from corehq.util.couch import get_db_by_doc_type
from dimagi.ext.jsonobject import JsonObject, StringProperty, ListProperty, DictProperty
from jsonobject.base_properties import DefaultProperty
from corehq.apps.userreports.expressions.getters import (
    DictGetter,
    NestedDictGetter,
    TransformedGetter,
    transform_from_datatype, transform_date, transform_int)
from corehq.apps.userreports.indicators.specs import DataTypeProperty
from corehq.apps.userreports.specs import TypeProperty, EvaluationContext
from corehq.util.quickcache import quickcache


class IdentityExpressionSpec(JsonObject):
    type = TypeProperty('identity')

    def __call__(self, item, context=None):
        return item


class ConstantGetterSpec(JsonObject):
    type = TypeProperty('constant')
    constant = DefaultProperty()

    @classmethod
    def wrap(self, obj):
        if 'constant' not in obj:
            raise BadSpecError('"constant" property is required!')
        return super(ConstantGetterSpec, self).wrap(obj)

    def __call__(self, item, context=None):
        return self.constant


class PropertyNameGetterSpec(JsonObject):
    type = TypeProperty('property_name')
    property_name = StringProperty(required=True)
    datatype = DataTypeProperty(required=False)

    @property
    def expression(self):
        transform = transform_from_datatype(self.datatype)
        getter = DictGetter(self.property_name)
        return TransformedGetter(getter, transform)

    def __call__(self, item, context=None):
        return self.expression(item, context)


class PropertyPathGetterSpec(JsonObject):
    type = TypeProperty('property_path')
    property_path = ListProperty(unicode, required=True)
    datatype = DataTypeProperty(required=False)

    @property
    def expression(self):
        transform = transform_from_datatype(self.datatype)
        getter = NestedDictGetter(self.property_path)
        return TransformedGetter(getter, transform)

    def __call__(self, item, context=None):
        return self.expression(item, context)


class NamedExpressionSpec(JsonObject):
    type = TypeProperty('named')
    name = StringProperty(required=True)

    def configure(self, context):
        if self.name not in context.named_expressions:
            raise BadSpecError(u'Name {} not found in list of named expressions!'.format(self.name))
        self._context = context

    def __call__(self, item, context=None):
        return self._context.named_expressions[self.name](item, context)


class ConditionalExpressionSpec(JsonObject):
    type = TypeProperty('conditional')
    test = DictProperty(required=True)
    expression_if_true = DefaultProperty(required=True)
    expression_if_false = DefaultProperty(required=True)

    def configure(self, test_function, true_expression, false_expression):
        self._test_function = test_function
        self._true_expression = true_expression
        self._false_expression = false_expression

    def __call__(self, item, context=None):
        if self._test_function(item, context):
            return self._true_expression(item, context)
        else:
            return self._false_expression(item, context)


class ArrayIndexExpressionSpec(JsonObject):
    type = TypeProperty('array_index')
    array_expression = DictProperty(required=True)
    index_expression = DefaultProperty(required=True)

    def configure(self, array_expression, index_expression):
        self._array_expression = array_expression
        self._index_expression = index_expression

    def __call__(self, item, context=None):
        array_value = self._array_expression(item, context)
        if not isinstance(array_value, list):
            return None

        index_value = self._index_expression(item, context)
        if not isinstance(index_value, int):
            return None

        try:
            return array_value[index_value]
        except IndexError:
            return None


class SwitchExpressionSpec(JsonObject):
    type = TypeProperty('switch')
    switch_on = DefaultProperty(required=True)
    cases = DefaultProperty(required=True)
    default = DefaultProperty(required=True)

    def configure(self, switch_on_expression, case_expressions, default_expression):
        self._switch_on_expression = switch_on_expression
        self._case_expressions = case_expressions
        self._default_expression = default_expression

    def __call__(self, item, context=None):
        switch_value = self._switch_on_expression(item, context)
        for c in self.cases:
            if switch_value == c:
                return self._case_expressions[c](item, context)
        return self._default_expression(item, context)


class IteratorExpressionSpec(JsonObject):
    type = TypeProperty('iterator')
    expressions = ListProperty(required=True)
    # an optional filter to test the values on - if they don't match they won't be included in the iteration
    test = DictProperty()

    def configure(self, expressions, test):
        self._expression_fns = expressions
        if test:
            self._test = test
        else:
            # if not defined then all values should be returned
            self._test = lambda *args, **kwargs: True

    def __call__(self, item, context=None):
        values = []
        for expression in self._expression_fns:
            value = expression(item, context)
            if self._test(value):
                values.append(value)
        return values


class RootDocExpressionSpec(JsonObject):
    type = TypeProperty('root_doc')
    expression = DictProperty(required=True)

    def configure(self, expression):
        self._expression_fn = expression

    def __call__(self, item, context=None):
        if context is None:
            return None
        return self._expression_fn(context.root_doc, context)


class RelatedDocExpressionSpec(JsonObject):
    type = TypeProperty('related_doc')
    related_doc_type = StringProperty()
    doc_id_expression = DictProperty(required=True)
    value_expression = DictProperty(required=True)

    def configure(self, doc_id_expression, value_expression):
        if get_db_by_doc_type(self.related_doc_type) is None:
            raise BadSpecError(u'Cannot determine database for document type {}!'.format(self.related_doc_type))

        self._doc_id_expression = doc_id_expression
        self._value_expression = value_expression
        # used in caching
        self._vary_on = json.dumps(self.value_expression, sort_keys=True)

    def __call__(self, item, context=None):
        doc_id = self._doc_id_expression(item, context)
        if doc_id:
            return self.get_value(doc_id, context)

    @quickcache(['self._vary_on', 'doc_id'])
    def get_value(self, doc_id, context):
        try:
            doc = get_db_by_doc_type(self.related_doc_type).get(doc_id)
            # ensure no cross-domain lookups of different documents
            assert context.root_doc['domain']
            if context.root_doc['domain'] != doc.get('domain'):
                return None
            # explicitly use a new evaluation context since this is a new document
            return self._value_expression(doc, EvaluationContext(doc, 0))
        except ResourceNotFound:
            return None


class NestedExpressionSpec(JsonObject):
    type = TypeProperty('nested')
    argument_expression = DictProperty(required=True)
    value_expression = DictProperty(required=True)

    def configure(self, argument_expression, value_expression):
        self._argument_expression = argument_expression
        self._value_expression = value_expression

    def __call__(self, item, context=None):
        argument = self._argument_expression(item, context)
        return self._value_expression(argument, context)


class DictExpressionSpec(JsonObject):
    type = TypeProperty('dict')
    properties = DictProperty(required=True)

    def configure(self, compiled_properties):
        for key in compiled_properties:
            if not isinstance(key, basestring):
                raise BadSpecError("Properties in a dict expression must be strings!")
        self._compiled_properties = compiled_properties

    def __call__(self, item, context=None):
        ret = {}
        for property_name, expression in self._compiled_properties.items():
            ret[property_name] = expression(item, context)
        return ret


class AddDaysExpressionSpec(JsonObject):
    type = TypeProperty('add_days')
    date_expression = DefaultProperty(required=True)
    count_expression = DefaultProperty(required=True)

    def configure(self, date_expression, count_expression):
        self._date_expression = date_expression
        self._count_expression = count_expression

    def __call__(self, item, context=None):
        date_val = transform_date(self._date_expression(item, context))
        int_val = transform_int(self._count_expression(item, context))
        if date_val is not None and int_val is not None:
            return date_val + timedelta(days=int_val)
        return None
