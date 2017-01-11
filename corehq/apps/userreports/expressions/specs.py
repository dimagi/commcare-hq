import json
from simpleeval import InvalidExpression
from corehq.apps.locations.document_store import LOCATION_DOC_TYPE
from corehq.apps.userreports.document_stores import get_document_store
from corehq.apps.userreports.exceptions import BadSpecError
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.util.couch import get_db_by_doc_type
from dimagi.ext.jsonobject import JsonObject, StringProperty, ListProperty, DictProperty
from jsonobject.base_properties import DefaultProperty
from corehq.apps.userreports.expressions.getters import transform_from_datatype, safe_recursive_lookup
from corehq.apps.userreports.indicators.specs import DataTypeProperty
from corehq.apps.userreports.specs import TypeProperty, EvaluationContext
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from pillowtop.dao.exceptions import DocumentNotFoundError
from .utils import eval_statements
from corehq.util.quickcache import quickcache


class IdentityExpressionSpec(JsonObject):
    type = TypeProperty('identity')

    def __call__(self, item, context=None):
        return item


class IterationNumberExpressionSpec(JsonObject):
    type = TypeProperty('base_iteration_number')

    def __call__(self, item, context=None):
        return context.iteration


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

    def __call__(self, item, context=None):
        raw_value = item.get(self.property_name, None) if isinstance(item, dict) else None
        return transform_from_datatype(self.datatype)(raw_value)


class PropertyPathGetterSpec(JsonObject):
    type = TypeProperty('property_path')
    property_path = ListProperty(unicode, required=True)
    datatype = DataTypeProperty(required=False)

    def __call__(self, item, context=None):
        transform = transform_from_datatype(self.datatype)
        return transform(safe_recursive_lookup(item, self.property_path))


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
        non_couch_doc_types = (LOCATION_DOC_TYPE,)
        if (self.related_doc_type not in non_couch_doc_types
                and get_db_by_doc_type(self.related_doc_type) is None):
            raise BadSpecError(u'Cannot determine database for document type {}!'.format(self.related_doc_type))

        self._doc_id_expression = doc_id_expression
        self._value_expression = value_expression

    def __call__(self, item, context=None):
        doc_id = self._doc_id_expression(item, context)
        if doc_id:
            return self.get_value(doc_id, context)

    def _context_cache_key(self, doc_id):
        return '{}-{}'.format(self.related_doc_type, doc_id)

    def get_value(self, doc_id, context):
        try:
            assert context.root_doc['domain']
            document_store = get_document_store(context.root_doc['domain'], self.related_doc_type)

            doc = context.get_cache_value(self._context_cache_key(doc_id))
            if not doc:
                doc = document_store.get_document(doc_id)
                context.set_cache_value(self._context_cache_key(doc_id), doc)
            # ensure no cross-domain lookups of different documents
            if context.root_doc['domain'] != doc.get('domain'):
                return None
            # explicitly use a new evaluation context since this is a new document
            return self._value_expression(doc, EvaluationContext(doc, 0))
        except DocumentNotFoundError:
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


class EvalExpressionSpec(JsonObject):
    type = TypeProperty('evaluator')
    statement = StringProperty(required=True)
    context_variables = DictProperty(required=True)
    datatype = DataTypeProperty(required=False)

    def configure(self, context_variables):
        self._context_variables = context_variables

    def __call__(self, item, context=None):
        var_dict = self.get_variables(item, context)
        try:
            untransformed_value = eval_statements(self.statement, var_dict)
            return transform_from_datatype(self.datatype)(untransformed_value)
        except (InvalidExpression, SyntaxError, TypeError, ZeroDivisionError):
            return None

    def get_variables(self, item, context):
        var_dict = {
            slug: variable_expression(item, context)
            for slug, variable_expression in self._context_variables.items()
        }
        return var_dict


class FormsExpressionSpec(JsonObject):
    type = TypeProperty('get_case_forms')
    case_id_expression = DefaultProperty(required=True)

    def configure(self, case_id_expression):
        self._case_id_expression = case_id_expression

    def __call__(self, item, context=None):
        case_id = self._case_id_expression(item, context)

        if not case_id:
            return []

        assert context.root_doc['domain']
        return self._get_forms(case_id, context)

    def _get_forms(self, case_id, context):
        domain = context.root_doc['domain']

        cache_key = (self.__class__.__name__, case_id)
        if context.get_cache_value(cache_key) is not None:
            return context.get_cache_value(cache_key)

        xforms = FormProcessorInterface(domain).get_case_forms(case_id)
        xforms = [f.to_json() for f in xforms if f.domain == domain]

        context.set_cache_value(cache_key, xforms)
        return xforms


class SubcasesExpressionSpec(JsonObject):
    type = TypeProperty('get_subcases')
    case_id_expression = DefaultProperty(required=True)

    def configure(self, case_id_expression):
        self._case_id_expression = case_id_expression

    def __call__(self, item, context=None):
        case_id = self._case_id_expression(item, context)
        if not case_id:
            return []

        assert context.root_doc['domain']
        return self._get_subcases(case_id, context)

    def _get_subcases(self, case_id, context):
        domain = context.root_doc['domain']
        cache_key = (self.__class__.__name__, case_id)
        if context.get_cache_value(cache_key) is not None:
            return context.get_cache_value(cache_key)

        subcases = [c.to_json() for c in CaseAccessors(domain).get_reverse_indexed_cases([case_id])]
        context.set_cache_value(cache_key, subcases)
        return subcases


class SplitStringExpressionSpec(JsonObject):
    type = TypeProperty('split_string')
    string_expression = DictProperty(required=True)
    index_expression = DefaultProperty(required=True)
    delimiter = StringProperty(required=False)

    def configure(self, string_expression, index_expression):
        self._string_expression = string_expression
        self._index_expression = index_expression

    def __call__(self, item, context=None):
        string_value = self._string_expression(item, context)
        if not isinstance(string_value, basestring):
            return None

        index_value = self._index_expression(item, context)
        if not isinstance(index_value, int):
            return None

        try:
            return string_value.split(self.delimiter)[index_value]
        except IndexError:
            return None
