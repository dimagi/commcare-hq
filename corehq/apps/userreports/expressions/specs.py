import json
from couchdbkit.exceptions import ResourceNotFound
from jsonobject import JsonObject, StringProperty, ListProperty, DictProperty
from jsonobject.base_properties import DefaultProperty
from corehq.apps.userreports.expressions.getters import DictGetter, NestedDictGetter
from corehq.apps.userreports.specs import TypeProperty
from corehq.util.quickcache import quickcache
from dimagi.utils.couch.database import get_db


class ConstantGetterSpec(JsonObject):
    type = TypeProperty('constant')
    constant = DefaultProperty(required=True)

    def __call__(self, item, context=None):
        return self.constant


class PropertyNameGetterSpec(JsonObject):
    type = TypeProperty('property_name')
    property_name = StringProperty(required=True)

    @property
    def expression(self):
        return DictGetter(self.property_name)

    def __call__(self, item, context=None):
        return self.expression(item, context)


class PropertyPathGetterSpec(JsonObject):
    type = TypeProperty('property_path')
    property_path = ListProperty(unicode, required=True)

    @property
    def expression(self):
        return NestedDictGetter(self.property_path)

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

        self._vary_on = json.dumps(self.value_expression)

    def __call__(self, item, context=None):
        doc_id = self._doc_id_expression(item, context)
        if doc_id:
            return self.get_value(doc_id, context)

    @quickcache(['self._vary_on', 'doc_id'])
    def get_value(self, doc_id, context):
        try:
            doc = self.db_lookup(self.related_doc_type).get(doc_id)

            return self._value_expression(doc, context)
        except ResourceNotFound:
            return None
