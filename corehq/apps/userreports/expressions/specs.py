import json
from couchdbkit.exceptions import ResourceNotFound
from dimagi.ext.jsonobject import JsonObject, StringProperty, ListProperty, DictProperty
from jsonobject.base_properties import DefaultProperty
from corehq.apps.userreports.expressions.getters import (
    DictGetter,
    NestedDictGetter,
    TransformedGetter,
    transform_from_datatype)
from corehq.apps.userreports.indicators.specs import DataTypeProperty
from corehq.apps.userreports.specs import TypeProperty, EvaluationContext
from corehq.util.quickcache import quickcache
from dimagi.utils.couch.database import get_db


class IdentityExpressionSpec(JsonObject):
    type = TypeProperty('identity')

    def __call__(self, item, context=None):
        return item


class ConstantGetterSpec(JsonObject):
    type = TypeProperty('constant')
    constant = DefaultProperty(required=True)

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


class ConditionalExpressionSpec(JsonObject):
    type = TypeProperty('conditional')
    test = DictProperty(required=True)
    expression_if_true = DictProperty(required=True)
    expression_if_false = DictProperty(required=True)

    def configure(self, test_function, true_expression, false_expression):
        self._test_function = test_function
        self._true_expression = true_expression
        self._false_expression = false_expression

    def __call__(self, item, context=None):
        if self._test_function(item, context):
            return self._true_expression(item, context)
        else:
            return self._false_expression(item, context)


class SwitchExpressionSpec(JsonObject):
    type = TypeProperty('switch')
    switch_on = DictProperty(required=True)
    cases = DictProperty(required=True)
    default = DictProperty(required=True)

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

    db_lookup = lambda self, type: get_db()

    def configure(self, related_doc_type, doc_id_expression, value_expression):
        self._related_doc_type = related_doc_type
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
            doc = self.db_lookup(self.related_doc_type).get(doc_id)
            # ensure no cross-domain lookups of different documents
            assert context.root_doc['domain']
            if context.root_doc['domain'] != doc.get('domain'):
                return None
            # explicitly use a new evaluation context since this is a new document
            return self._value_expression(doc, EvaluationContext(doc, 0))
        except ResourceNotFound:
            return None
