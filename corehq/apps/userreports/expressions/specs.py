from __future__ import absolute_import
import hashlib
import json
from exceptions import NotImplementedError

from django.core.serializers.json import DjangoJSONEncoder
from jsonobject.base_properties import DefaultProperty
from simpleeval import InvalidExpression
import six

from corehq.apps.locations.document_store import LOCATION_DOC_TYPE
from corehq.apps.userreports.const import XFORM_CACHE_KEY_PREFIX
from corehq.apps.userreports.decorators import ucr_context_cache
from corehq.apps.userreports.document_stores import get_document_store
from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.util.couch import get_db_by_doc_type
from corehq.apps.userreports.expressions.getters import transform_from_datatype, safe_recursive_lookup
from corehq.apps.userreports.indicators.specs import DataTypeProperty
from corehq.apps.userreports.specs import TypeProperty, EvaluationContext
from corehq.apps.userreports.util import add_tabbed_text
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from dimagi.ext.jsonobject import JsonObject, StringProperty, ListProperty, DictProperty
from pillowtop.dao.exceptions import DocumentNotFoundError
from .utils import eval_statements


class IdentityExpressionSpec(JsonObject):
    type = TypeProperty('identity')

    def __call__(self, item, context=None):
        return item

    def __str__(self):
        return "doc"


class IterationNumberExpressionSpec(JsonObject):
    type = TypeProperty('base_iteration_number')

    def __call__(self, item, context=None):
        return context.iteration

    def __str__(self):
        return "Iteration Count"


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

    def __str__(self):
        return '{}'.format(self.constant)


class PropertyNameGetterSpec(JsonObject):
    type = TypeProperty('property_name')
    property_name = DefaultProperty(required=True)
    datatype = DataTypeProperty(required=False)

    def configure(self, property_name_expression):
        self._property_name_expression = property_name_expression

    def __call__(self, item, context=None):
        raw_value = item.get(self._property_name_expression(item, context)) if isinstance(item, dict) else None
        return transform_from_datatype(self.datatype)(raw_value)

    def __str__(self):
        value = self.property_name
        if self.datatype:
            "({datatype}){value}".format(datatype=self.datatype, value=value)
        return value


class PropertyPathGetterSpec(JsonObject):
    type = TypeProperty('property_path')
    property_path = ListProperty(six.text_type, required=True)
    datatype = DataTypeProperty(required=False)

    def __call__(self, item, context=None):
        transform = transform_from_datatype(self.datatype)
        return transform(safe_recursive_lookup(item, self.property_path))

    def __str__(self):
        value = "/".join(self.property_path)
        if self.datatype:
            "({datatype}){value}".format(datatype=self.datatype, value=value)
        return value


class NamedExpressionSpec(JsonObject):
    type = TypeProperty('named')
    name = StringProperty(required=True)

    def configure(self, context):
        if self.name not in context.named_expressions:
            raise BadSpecError(u'Name {} not found in list of named expressions!'.format(self.name))
        self._context = context

    def _context_cache_key(self, item):
        item_hash = hashlib.md5(json.dumps(item, cls=DjangoJSONEncoder, sort_keys=True)).hexdigest()
        return 'named_expression-{}-{}'.format(self.name, item_hash)

    def __call__(self, item, context=None):
        key = self._context_cache_key(item)
        if context and context.exists_in_cache(key):
            return context.get_cache_value(key)

        result = self._context.named_expressions[self.name](item, context)
        if context:
            context.set_iteration_cache_value(key, result)
        return result

    def __str__(self):
        return "NamedExpression:{}".format(self.name)


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

    def __str__(self):
        return "if {test}:\n{true}\nelse:\n{false}".format(
            test=str(self._test_function),
            true=add_tabbed_text(str(self._true_expression)),
            false=add_tabbed_text(str(self._false_expression)))


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

    def __str__(self):
        return "{}[{}]".format(str(self._array_expression), str(self._index_expression))


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

    def __str__(self):
        map_text = ", ".join(
            ["{}:{}".format(c, str(self._case_expressions[c])) for c in self.cases]
        )
        return "switch:{expression}:\n{map}\ndefault:\n{default}".format(
            expression=str(self._switch_on_expression),
            map=add_tabbed_text(map_text),
            default=add_tabbed_text((str(self._default_expression))))


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

    def __str__(self):
        expressions_text = ", ".join(str(e) for e in self._expression_fns)
        return "iterate on [{}] if {}".format(expressions_text, str(self._test))


class RootDocExpressionSpec(JsonObject):
    type = TypeProperty('root_doc')
    expression = DictProperty(required=True)

    def configure(self, expression):
        self._expression_fn = expression

    def __call__(self, item, context=None):
        if context is None:
            return None
        return self._expression_fn(context.root_doc, context)

    def __str__(self):
        return "doc/{expression}".format(expression=str(self._expression_fn))


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

    @staticmethod
    @ucr_context_cache(vary_on=('related_doc_type', 'doc_id',))
    def _get_document(related_doc_type, doc_id, context):
        document_store = get_document_store(context.root_doc['domain'], related_doc_type)
        try:
            doc = document_store.get_document(doc_id)
        except DocumentNotFoundError:
            return None
        if context.root_doc['domain'] != doc.get('domain'):
            return None
        return doc

    def get_value(self, doc_id, context):
        assert context.root_doc['domain']
        doc = self._get_document(self.related_doc_type, doc_id, context)
        # explicitly use a new evaluation context since this is a new document
        return self._value_expression(doc, EvaluationContext(doc, 0))

    def __str__(self):
        return "{}[{}]/{}".format(self.related_doc_type,
                                  str(self._doc_id_expression),
                                  str(self._value_expression))


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

    def __str__(self):
        return "{arg}/{val}".format(val=str(self._value_expression), arg=str(self._argument_expression))


class DictExpressionSpec(JsonObject):
    type = TypeProperty('dict')
    properties = DictProperty(required=True)

    def configure(self, compiled_properties):
        for key in compiled_properties:
            if not isinstance(key, six.string_types):
                raise BadSpecError("Properties in a dict expression must be strings!")
        self._compiled_properties = compiled_properties

    def __call__(self, item, context=None):
        ret = {}
        for property_name, expression in self._compiled_properties.items():
            ret[property_name] = expression(item, context)
        return ret

    def __str__(self):
        dict_text = ", ".join(
            ["{}:{}".format(name, str(exp)) for name, exp in self._compiled_properties.items()]
        )
        return "({})".format(dict_text)


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

    def __str__(self):
        value = self.statement
        for name, exp in self._context_variables.items():
            value.replace(name, str(exp))
        if self.datatype:
            value = "({}){}".format(self.datatype, value)
        return value


class FormsExpressionSpec(JsonObject):
    type = TypeProperty('get_case_forms')
    case_id_expression = DefaultProperty(required=True)
    xmlns = ListProperty(required=False)

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

        cache_key = (self.__class__.__name__, case_id, tuple(self.xmlns))
        if context.get_cache_value(cache_key) is not None:
            return context.get_cache_value(cache_key)

        xforms = self._get_case_forms(case_id, context)
        if self.xmlns:
            xforms = [f for f in xforms if f.xmlns in self.xmlns]

        xforms = [self._get_form_json(f, context) for f in xforms if f.domain == domain]

        context.set_cache_value(cache_key, xforms)
        return xforms

    @ucr_context_cache(vary_on=('case_id',))
    def _get_case_forms(self, case_id, context):
        domain = context.root_doc['domain']
        return FormProcessorInterface(domain).get_case_forms(case_id)

    def _get_form_json(self, form, context):
        cache_key = (XFORM_CACHE_KEY_PREFIX, form.get_id)
        if context.get_cache_value(cache_key) is not None:
            return context.get_cache_value(cache_key)

        form_json = form.to_json()
        context.set_cache_value(cache_key, form_json)
        return form_json

    def __str__(self):
        xmlns_text = ", ".join(self.xmlns)
        if xmlns_text:
            form_text = "({})".format(xmlns_text)
        else:
            form_text = "all"
        return "get {} forms for {}".format(form_text, str(self._case_id_expression))


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

    @ucr_context_cache(vary_on=('case_id',))
    def _get_subcases(self, case_id, context):
        domain = context.root_doc['domain']
        return [c.to_json() for c in CaseAccessors(domain).get_reverse_indexed_cases([case_id])]

    def __str__(self):
        return "get subcases for {}".format(str(self._case_id_expression))


class _GroupsExpressionSpec(JsonObject):
    user_id_expression = DictProperty(required=True)

    def configure(self, user_id_expression):
        self._user_id_expression = user_id_expression

    def __call__(self, item, context=None):
        user_id = self._user_id_expression(item, context)
        if not user_id:
            return []

        assert context.root_doc['domain']
        return self._get_groups(user_id, context)

    @ucr_context_cache(vary_on=('user_id',))
    def _get_groups(self, user_id, context):
        domain = context.root_doc['domain']
        user = CommCareUser.get_by_user_id(user_id, domain)
        if not user:
            return []

        groups = self._get_groups_from_user(user)
        return [g.to_json() for g in groups]

    def _get_groups_from_user(self, user):
        raise NotImplementedError


class CaseSharingGroupsExpressionSpec(_GroupsExpressionSpec):
    type = TypeProperty('get_case_sharing_groups')

    def _get_groups_from_user(self, user):
        return user.get_case_sharing_groups()

    def __str__(self):
        return "get case sharing groups for {}".format(str(self._user_id_expression))


class ReportingGroupsExpressionSpec(_GroupsExpressionSpec):
    type = TypeProperty('get_reporting_groups')

    def _get_groups_from_user(self, user):
        return user.get_reporting_groups()

    def __str__(self):
        return "get reporting groups for {}".format(str(self._user_id_expression))


class SplitStringExpressionSpec(JsonObject):
    type = TypeProperty('split_string')
    string_expression = DictProperty(required=True)
    index_expression = DefaultProperty(required=False)
    delimiter = StringProperty(required=False)

    def configure(self, string_expression, index_expression):
        self._string_expression = string_expression
        self._index_expression = index_expression

    def __call__(self, item, context=None):
        string_value = self._string_expression(item, context)
        if not isinstance(string_value, six.string_types):
            return None

        index_value = None
        if self.index_expression is not None:
            index_value = self._index_expression(item, context)
            if not isinstance(index_value, int):
                return None

        try:
            split = string_value.split(self.delimiter)
            return split[index_value] if index_value is not None else split
        except IndexError:
            return None

    def __str__(self):
        split_text = "split {}".format(str(self._string_expression))
        if self.delimiter:
            split_text += " on '{}'".format(self.delimiter)
        return "(split {})[{}]".format(str(split_text), str(self._index_expression))


class CoalesceExpressionSpec(JsonObject):
    type = TypeProperty('coalesce')
    expression = DictProperty(required=True)
    default_expression = DictProperty(required=True)

    def configure(self, expression, default_expression):
        self._expression = expression
        self._default_expression = default_expression

    def __call__(self, item, context=None):
        expression_value = self._expression(item, context)
        default_value = self._default_expression(item, context)
        if expression_value is None or expression_value == '':
            return default_value
        else:
            return expression_value

    def __str__(self):
        return "coalesce({}, {})".format(str(self._expression), str(self._default_expression))
