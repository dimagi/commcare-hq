import textwrap
from functools import cached_property

from jsonobject.base_properties import DefaultProperty
from jsonpath_ng.ext import parse as jsonpath_parse
from simpleeval import InvalidExpression

from dimagi.ext.jsonobject import (
    DictProperty,
    JsonObject,
    ListProperty,
    StringProperty,
)
from pillowtop.dao.exceptions import DocumentNotFoundError

from corehq.apps.change_feed.data_sources import (
    get_document_store_for_doc_type,
)
from corehq.apps.locations.document_store import LOCATION_DOC_TYPE
from corehq.apps.userreports.const import (
    NAMED_EXPRESSION_PREFIX,
    XFORM_CACHE_KEY_PREFIX,
)
from corehq.apps.userreports.datatypes import DataTypeProperty
from corehq.apps.userreports.decorators import ucr_context_cache
from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.expressions.getters import (
    safe_recursive_lookup,
    transform_for_datatype,
)
from corehq.apps.userreports.mixins import NoPropertyTypeCoercionMixIn
from corehq.apps.userreports.specs import EvaluationContext, TypeProperty
from corehq.apps.userreports.util import add_tabbed_text
from corehq.apps.users.models import CommCareUser, CouchUser
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.form_processor.models import CommCareCase, XFormInstance
from corehq.util.couch import get_db_by_doc_type

from .evaluator import eval_statements, EvalExecutionContext


class IdentityExpressionSpec(JsonObject):
    type = TypeProperty('identity')

    def __call__(self, item, evaluation_context=None):
        return item

    def __str__(self):
        return "doc"


class IterationNumberExpressionSpec(JsonObject):
    """
    These are very simple expressions with no config. They return the index
    of the repeat item starting from 0 when used with a
    ``base_item_expression``.

    .. code:: json

       {
           "type": "base_iteration_number"
       }
    """
    type = TypeProperty('base_iteration_number')

    def __call__(self, item, evaluation_context=None):
        return evaluation_context.iteration

    def __str__(self):
        return "Iteration Count"


class ConstantGetterSpec(JsonObject):
    """
    There are two formats for constant expressions. The simplified format is
    simply the constant itself. For example ``"hello"``, or ``5``.

    The complete format is as follows. This expression returns the constant
    ``"hello"``:

    .. code:: json

       {
           "type": "constant",
           "constant": "hello"
       }
    """
    type = TypeProperty('constant')
    constant = DefaultProperty()

    @classmethod
    def wrap(self, obj):
        if 'constant' not in obj:
            raise BadSpecError('"constant" property is required in object beginning with <pre>{}</pre>'.format(
                textwrap.shorten(str(obj), width=75, placeholder="...")
            ))
        return super(ConstantGetterSpec, self).wrap(obj)

    def __call__(self, item, evaluation_context=None):
        return self.constant

    def __str__(self):
        return '{}'.format(self.constant)


class PropertyNameGetterSpec(JsonObject):
    """
    This expression returns ``doc["age"]``:

    .. code:: json

       {
           "type": "property_name",
           "property_name": "age"
       }

    An optional ``"datatype"`` attribute may be specified, which will
    attempt to cast the property to the given data type. The options are
    "date", "datetime", "string", "integer", and "decimal". If no datatype
    is specified, "string" will be used.
    """
    type = TypeProperty('property_name')
    property_name = DefaultProperty(required=True)
    datatype = DataTypeProperty(required=False)

    def configure(self, property_name_expression):
        self._property_name_expression = property_name_expression

    def __call__(self, item, evaluation_context=None):
        raw_value = None
        if isinstance(item, dict):
            raw_value = item.get(self._property_name_expression(item, evaluation_context))
        return transform_for_datatype(self.datatype)(raw_value)

    def __str__(self):
        value = self.property_name
        if self.datatype:
            "({datatype}){value}".format(datatype=self.datatype, value=value)
        return value


class PropertyPathGetterSpec(JsonObject):
    """
    This expression returns ``doc["child"]["age"]``:

    .. code:: json

       {
           "type": "property_path",
           "property_path": ["child", "age"]
       }

    An optional ``"datatype"`` attribute may be specified, which will
    attempt to cast the property to the given data type. The options are
    "date", "datetime", "string", "integer", and "decimal". If no datatype
    is specified, "string" will be used.
    """
    type = TypeProperty('property_path')
    property_path = ListProperty(str, required=True)
    datatype = DataTypeProperty(required=False)

    def __call__(self, item, evaluation_context=None):
        transform = transform_for_datatype(self.datatype)
        return transform(safe_recursive_lookup(item, self.property_path))

    def __str__(self):
        value = "/".join(self.property_path)
        if self.datatype:
            "({datatype}){value}".format(datatype=self.datatype, value=value)
        return value


class NamedExpressionSpec(JsonObject):
    """
    Last, but certainly not least, are named expressions. These are special
    expressions that can be defined once in a data source and then used
    throughout other filters and indicators in that data source. This allows
    you to write out a very complicated expression a single time, but still
    use it in multiple places with a simple syntax.

    Named expressions are defined in a special section of the data source.
    To reference a named expression, you just specify the type of
    ``"named"`` and the name as follows:

    .. code:: json

       {
           "type": "named",
           "name": "my_expression"
       }

    This assumes that your named expression section of your data source
    includes a snippet like the following:

    .. code:: json

       {
           "my_expression": {
               "type": "property_name",
               "property_name": "test"
           }
       }

    This is just a simple example - the value that ``"my_expression"`` takes
    on can be as complicated as you want and it can also reference other named
    expressions as long as it doesn't reference itself of create a recursive cycle.

    See also the :any:`named` evaluator function.
    """
    type = TypeProperty('named')
    name = StringProperty(required=True)

    def configure(self, factory_context):
        if self.name not in factory_context.named_expressions:
            raise BadSpecError('Name {} not found in list of named expressions!'.format(self.name))
        self._factory_context = factory_context

    def _context_cache_key(self, item):
        return 'named_expression-{}-{}'.format(self.name, id(item))

    def __call__(self, item, evaluation_context=None):
        key = self._context_cache_key(item)
        if evaluation_context and evaluation_context.exists_in_cache(key):
            return evaluation_context.get_cache_value(key)

        result = self._factory_context.named_expressions[self.name](item, evaluation_context)
        if evaluation_context:
            evaluation_context.set_iteration_cache_value(key, result)
        return result

    def __str__(self):
        return "{}:{}".format(NAMED_EXPRESSION_PREFIX, self.name)


class ConditionalExpressionSpec(JsonObject):
    """
    This expression returns ``"legal" if doc["age"] > 21 else "underage"``:

    .. code:: json

       {
           "type": "conditional",
           "test": {
               "operator": "gt",
               "expression": {
                   "type": "property_name",
                   "property_name": "age",
                   "datatype": "integer"
               },
               "type": "boolean_expression",
               "property_value": 21
           },
           "expression_if_true": {
               "type": "constant",
               "constant": "legal"
           },
           "expression_if_false": {
               "type": "constant",
               "constant": "underage"
           }
       }

    Note that this expression contains other expressions inside it! This is
    why expressions are powerful. (It also contains a filter, but we haven't
    covered those yet - if you find the ``"test"`` section confusing, keep
    reading...)

    Note also that it's important to make sure that you are comparing values
    of the same type. In this example, the expression that retrieves the age
    property from the document also casts the value to an integer. If this
    datatype is not specified, the expression will compare a string to the
    ``21`` value, which will not produce the expected results!
    """
    type = TypeProperty('conditional')
    test = DictProperty(required=True)
    expression_if_true = DefaultProperty(required=True)
    expression_if_false = DefaultProperty(required=True)

    def configure(self, test_function, true_expression, false_expression):
        self._test_function = test_function
        self._true_expression = true_expression
        self._false_expression = false_expression

    def __call__(self, item, evaluation_context=None):
        if self._test_function(item, evaluation_context):
            return self._true_expression(item, evaluation_context)
        else:
            return self._false_expression(item, evaluation_context)

    def __str__(self):
        return "if {test}:\n{true}\nelse:\n{false}".format(
            test=str(self._test_function),
            true=add_tabbed_text(str(self._true_expression)),
            false=add_tabbed_text(str(self._false_expression)))


class ArrayIndexExpressionSpec(NoPropertyTypeCoercionMixIn, JsonObject):
    """
    This expression returns ``doc["siblings"][0]``:

    .. code:: json

       {
           "type": "array_index",
           "array_expression": {
               "type": "property_name",
               "property_name": "siblings"
           },
           "index_expression": {
               "type": "constant",
               "constant": 0
           }
       }

    It will return nothing if the siblings property is not a list, the index
    isn't a number, or the indexed item doesn't exist.
    """
    type = TypeProperty('array_index')
    array_expression = DictProperty(required=True)
    index_expression = DefaultProperty(required=True)

    def configure(self, array_expression, index_expression):
        self._array_expression = array_expression
        self._index_expression = index_expression

    def __call__(self, item, evaluation_context=None):
        array_value = self._array_expression(item, evaluation_context)
        if not isinstance(array_value, list):
            return None

        index_value = self._index_expression(item, evaluation_context)
        if not isinstance(index_value, int):
            return None

        try:
            return array_value[index_value]
        except IndexError:
            return None

    def __str__(self):
        return "{}[{}]".format(str(self._array_expression), str(self._index_expression))


class SwitchExpressionSpec(JsonObject):
    """
    This expression returns the value of the expression for the case that
    matches the switch on expression. Note that case values may only be
    strings at this time.

    .. code:: json

       {
           "type": "switch",
           "switch_on": {
               "type": "property_name",
               "property_name": "district"
           },
           "cases": {
               "north": {
                   "type": "constant",
                   "constant": 4000
               },
               "south": {
                   "type": "constant",
                   "constant": 2500
               },
               "east": {
                   "type": "constant",
                   "constant": 3300
               },
               "west": {
                   "type": "constant",
                   "constant": 65
               },
           },
           "default": {
               "type": "constant",
               "constant": 0
           }
       }
    """
    type = TypeProperty('switch')
    switch_on = DefaultProperty(required=True)
    cases = DefaultProperty(required=True)
    default = DefaultProperty(required=True)

    def configure(self, switch_on_expression, case_expressions, default_expression):
        self._switch_on_expression = switch_on_expression
        self._case_expressions = case_expressions
        self._default_expression = default_expression

    def __call__(self, item, evaluation_context=None):
        switch_value = self._switch_on_expression(item, evaluation_context)
        for c in self.cases:
            if switch_value == c:
                return self._case_expressions[c](item, evaluation_context)
        return self._default_expression(item, evaluation_context)

    def __str__(self):
        map_text = ", ".join(
            ["{}:{}".format(c, str(self._case_expressions[c])) for c in self.cases]
        )
        return "switch:{expression}:\n{map}\ndefault:\n{default}".format(
            expression=str(self._switch_on_expression),
            map=add_tabbed_text(map_text),
            default=add_tabbed_text((str(self._default_expression))))


class IteratorExpressionSpec(NoPropertyTypeCoercionMixIn, JsonObject):
    """
    .. code:: json

       {
           "type": "iterator",
           "expressions": [
               {
                   "type": "property_name",
                   "property_name": "p1"
               },
               {
                   "type": "property_name",
                   "property_name": "p2"
               },
               {
                   "type": "property_name",
                   "property_name": "p3"
               },
           ],
           "test": {}
       }

    This will emit ``[doc.p1, doc.p2, doc.p3]``. You can add a ``test``
    attribute to filter rows from what is emitted - if you don't specify
    this then the iterator will include one row per expression it contains
    regardless of what is passed in. This can be used/combined with the
    ``base_item_expression`` to emit multiple rows per document.
    """
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

    def __call__(self, item, evaluation_context=None):
        values = []
        for expression in self._expression_fns:
            value = expression(item, evaluation_context)
            if self._test(value):
                values.append(value)
        return values

    def __str__(self):
        expressions_text = ", ".join(str(e) for e in self._expression_fns)
        return "iterate on [{}] if {}".format(expressions_text, str(self._test))


class JsonpathExpressionSpec(NoPropertyTypeCoercionMixIn, JsonObject):
    """
    This will execute the jsonpath expression against the current doc
    and emit the result.

    .. code:: json

       {
           "type": "jsonpath",
           "jsonpath": "form..case.name",
       }

    Given the following doc:

    .. code:: json

        {
            "form": {
                "case": {"name": "a"},
                "nested": {
                    "case": {"name": "b"},
                },
                "list": [
                    {"case": {"name": "c"}},
                    {
                        "nested": {
                            "case": {"name": "d"}
                        }
                    }
                ]
            }
        }

    This above expression will evaluate to ``["a", "b", "c", "d"]``.
    Another example is ``form.list[0].case.name`` which will evaluate to ``"c"``.

    See also the :any:`jsonpath` evaluator function.

    For more information consult the following resources:

    * `Article by Stefan Goessner <https://goessner.net/articles/JsonPath/>`__
    * `JSONPath expression syntax <https://goessner.net/articles/JsonPath/index.html#e2>`__
    * `JSONPath Online Evaluator <https://jsonpath.com/>`__
    """
    type = TypeProperty('jsonpath')
    jsonpath = StringProperty(str, required=True)
    datatype = DataTypeProperty(required=False)

    @classmethod
    def wrap(cls, obj):
        ret = super().wrap(obj)
        ret.jsonpath_expr  # noqa: call to validate
        return ret

    @cached_property
    def jsonpath_expr(self):
        try:
            return jsonpath_parse(self.jsonpath)
        except Exception as e:
            raise BadSpecError(f'Error parsing jsonpath expression <pre>{self.jsonpath}</pre>. '
                               f'Message is {str(e)}')

    def __call__(self, item, evaluation_context=None):
        transform = transform_for_datatype(self.datatype)
        values = [transform(match.value) for match in self.jsonpath_expr.find(item)]
        if not values:
            return None
        if len(values) == 1:
            return values[0]
        return values

    def __str__(self):
        if self.datatype:
            return f"({self.datatype}){self.jsonpath}"
        return self.jsonpath


class RootDocExpressionSpec(JsonObject):
    type = TypeProperty('root_doc')
    expression = DictProperty(required=True)

    def configure(self, expression):
        self._expression_fn = expression

    def __call__(self, item, evaluation_context=None):
        if evaluation_context is None:
            return None
        return self._expression_fn(evaluation_context.root_doc, evaluation_context)

    def __str__(self):
        return "doc/{expression}".format(expression=str(self._expression_fn))


class RelatedDocExpressionSpec(JsonObject):
    """
    This can be used to lookup a property in another document. Here's an
    example that lets you look up ``form.case.owner_id`` from a form.

    .. code:: json

       {
           "type": "related_doc",
           "related_doc_type": "CommCareCase",
           "doc_id_expression": {
               "type": "property_path",
               "property_path": ["form", "case", "@case_id"]
           },
           "value_expression": {
               "type": "property_name",
               "property_name": "owner_id"
           }
       }
    """
    type = TypeProperty('related_doc')
    related_doc_type = StringProperty()
    doc_id_expression = DictProperty(required=True)
    value_expression = DictProperty(required=True)

    def configure(self, doc_id_expression, value_expression):
        non_couch_doc_types = {
            CommCareCase.DOC_TYPE,
            LOCATION_DOC_TYPE,
            XFormInstance.STATE_TO_DOC_TYPE[XFormInstance.NORMAL],
        }
        if (self.related_doc_type not in non_couch_doc_types
                and get_db_by_doc_type(self.related_doc_type) is None):
            raise BadSpecError('Cannot determine database for document type {}!'.format(self.related_doc_type))

        self._doc_id_expression = doc_id_expression
        self._value_expression = value_expression

    def __call__(self, item, evaluation_context=None):
        doc_id = self._doc_id_expression(item, evaluation_context)
        if doc_id:
            return self.get_value(doc_id, evaluation_context)

    @staticmethod
    @ucr_context_cache(vary_on=('related_doc_type', 'doc_id',))
    def _get_document(related_doc_type, doc_id, evaluation_context):
        document_store = get_document_store_for_doc_type(
            evaluation_context.root_doc['domain'], related_doc_type,
            load_source="related_doc_expression")
        try:
            doc = document_store.get_document(doc_id)
        except DocumentNotFoundError:
            return None
        if evaluation_context.root_doc['domain'] != doc.get('domain'):
            return None
        return doc

    def get_value(self, doc_id, evaluation_context):
        assert evaluation_context.root_doc['domain']
        doc = self._get_document(self.related_doc_type, doc_id, evaluation_context)
        # explicitly use a new evaluation context since this is a new document
        return self._value_expression(doc, EvaluationContext(doc, 0))

    def __str__(self):
        return "{}[{}]/{}".format(self.related_doc_type,
                                  str(self._doc_id_expression),
                                  str(self._value_expression))


class NestedExpressionSpec(JsonObject):
    """
    These can be used to nest expressions. This can be used, e.g. to pull a
    specific property out of an item in a list of objects.

    The following nested expression is the equivalent of a ``property_path``
    expression to ``["outer", "inner"]`` and demonstrates the functionality.
    More examples can be found in the `practical examples`_.

    .. code:: json

       {
           "type": "nested",
           "argument_expression": {
               "type": "property_name",
               "property_name": "outer"
           },
           "value_expression": {
               "type": "property_name",
               "property_name": "inner"
           }
       }
    """
    type = TypeProperty('nested')
    argument_expression = DictProperty(required=True)
    value_expression = DictProperty(required=True)

    def configure(self, argument_expression, value_expression):
        self._argument_expression = argument_expression
        self._value_expression = value_expression

    def __call__(self, item, evaluation_context=None):
        argument = self._argument_expression(item, evaluation_context)
        return self._value_expression(argument, evaluation_context)

    def __str__(self):
        return "{arg}/{val}".format(val=str(self._value_expression), arg=str(self._argument_expression))


class DictExpressionSpec(JsonObject):
    """
    These can be used to create dictionaries of key/value pairs. This is
    only useful as an intermediate structure in another expression since the
    result of the expression is a dictionary that cannot be saved to the
    database.

    See the `practical examples`_
    for a way this can be used in a ``base_item_expression`` to emit
    multiple rows for a single form/case based on different properties.

    Here is a simple example that demonstrates the structure. The keys of
    ``properties`` must be text, and the values must be valid expressions
    (or constants):

    .. code:: json

       {
           "type": "dict",
           "properties": {
               "name": "a constant name",
               "value": {
                   "type": "property_name",
                   "property_name": "prop"
               },
               "value2": {
                   "type": "property_name",
                   "property_name": "prop2"
               }
           }
       }
    """
    type = TypeProperty('dict')
    properties = DictProperty(required=True)

    def configure(self, compiled_properties):
        for key in compiled_properties:
            if not isinstance(key, str):
                raise BadSpecError("Properties in a dict expression must be strings!")
        self._compiled_properties = compiled_properties

    def __call__(self, item, evaluation_context=None):
        ret = {}
        for property_name, expression in self._compiled_properties.items():
            ret[property_name] = expression(item, evaluation_context)
        return ret

    def __str__(self):
        dict_text = ", ".join(
            ["{}:{}".format(name, str(exp)) for name, exp in self._compiled_properties.items()]
        )
        return "({})".format(dict_text)


class EvalExpressionSpec(JsonObject):
    """
    ``evaluator`` expression can be used to evaluate statements that contain
    arithmetic (and simple python like statements). It evaluates the
    statement specified by ``statement`` which can contain variables as
    defined in ``context_variables``.

    .. code:: json

       {
           "type": "evaluator",
           "statement": "a + b - c + 6",
           "context_variables": {
               "a": 1,
               "b": 20,
               "c": {
                   "type": "property_name",
                   "property_name": "the_number_two"
               }
           }
       }

    This returns **25** (1 + 20 - 2 + 6).

    ``statement``

        The expression statement to be evaluated.

    ``context_variables``

        A dictionary of Expressions where keys are names of variables used in the ``statement``
        and values are expressions to generate those variables.

        Variable types must be one of:

        -  ``str``
        -  ``int``
        -  ``float``
        -  ``bool``
        -  ``date``
        -  ``datetime``

         If ``context_variables`` is omitted, the current context of the expression will be used.

    **Expression limitations**

        Only a single expression is permitted.

        Available operators:

        - `math operators`_ (except the power operator)
        - `modulus`_
        - `negation`_
        - `comparison operators`_
        - `logical operators`_

        In addition, expressions can perform the following operations:

        - index: `case['name']`
        - slice: `cases[0:2]`
        - if statements: `1 if case.name == 'bob' else 0`
        - list comprehension: `[i for i in range(3)]`
        - dict, list, set construction: `{"a": 1, "b": set(cases), "c": list(range(4))}`

    **Available Functions**

        Only the following functions are available in the evaluation context:

        .. include:: ../corehq/apps/userreports/expressions/evaluator/FUNCTION_DOCS.rst

    .. _math operators: https://en.wikibooks.org/wiki/Python_Programming/Basic_Math#Mathematical_Operators
    .. _modulus: https://en.wikibooks.org/wiki/Python_Programming/Operators#Modulus
    .. _negation: https://en.wikibooks.org/wiki/Python_Programming/Operators#Negation
    .. _comparison operators: https://en.wikibooks.org/wiki/Python_Programming/Operators#Comparison
    .. _logical operators: https://en.wikibooks.org/wiki/Python_Programming/Operators#Logical_Operators

    See also :ref:`ucr-evaluator-examples`.
    """
    type = TypeProperty('evaluator')
    statement = StringProperty(required=True)
    context_variables = DictProperty()
    datatype = DataTypeProperty(required=False)

    def configure(self, factory_context):
        self._factory_context = factory_context
        self._context_variables = {
            slug: factory_context.expression_from_spec(expression)
            for slug, expression in self.context_variables.items()
        }

    def __call__(self, item, evaluation_context=None):
        var_dict = self.get_variables(item, evaluation_context)
        try:
            untransformed_value = eval_statements(self.statement, var_dict, EvalExecutionContext(
                evaluation_context, self._factory_context
            ))
            return transform_for_datatype(self.datatype)(untransformed_value)
        except (InvalidExpression, SyntaxError, TypeError, ZeroDivisionError):
            return None

    def get_variables(self, item, evaluation_context):
        if not self._context_variables and isinstance(item, dict):
            return IdentityExpressionSpec(type='identity')(item, evaluation_context)

        var_dict = {
            slug: variable_expression(item, evaluation_context)
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

    def __call__(self, item, evaluation_context=None):
        case_id = self._case_id_expression(item, evaluation_context)

        if not case_id:
            return []

        assert evaluation_context.root_doc['domain']
        return self._get_forms(case_id, evaluation_context)

    def _get_forms(self, case_id, evaluation_context):
        domain = evaluation_context.root_doc['domain']

        cache_key = (self.__class__.__name__, case_id, tuple(self.xmlns))
        if evaluation_context.get_cache_value(cache_key) is not None:
            return evaluation_context.get_cache_value(cache_key)

        xforms = self._get_case_forms(case_id, evaluation_context)
        if self.xmlns:
            xforms = [f for f in xforms if f.xmlns in self.xmlns]

        xforms = [self._get_form_json(f, evaluation_context) for f in xforms if f.domain == domain]

        evaluation_context.set_cache_value(cache_key, xforms)
        return xforms

    @ucr_context_cache(vary_on=('case_id',))
    def _get_case_forms(self, case_id, evaluation_context):
        domain = evaluation_context.root_doc['domain']
        return FormProcessorInterface(domain).get_case_forms(case_id)

    def _get_form_json(self, form, evaluation_context):
        cache_key = (XFORM_CACHE_KEY_PREFIX, form.get_id)
        if evaluation_context.get_cache_value(cache_key) is not None:
            return evaluation_context.get_cache_value(cache_key)

        form_json = form.to_json()
        evaluation_context.set_cache_value(cache_key, form_json)
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

    def __call__(self, item, evaluation_context=None):
        case_id = self._case_id_expression(item, evaluation_context)
        if not case_id:
            return []

        assert evaluation_context.root_doc['domain']
        return self._get_subcases(case_id, evaluation_context)

    @ucr_context_cache(vary_on=('case_id',))
    def _get_subcases(self, case_id, evaluation_context):
        domain = evaluation_context.root_doc['domain']
        return [c.to_json() for c in CommCareCase.objects.get_reverse_indexed_cases(domain, [case_id])]

    def __str__(self):
        return "get subcases for {}".format(str(self._case_id_expression))


class _GroupsExpressionSpec(JsonObject):
    user_id_expression = DictProperty(required=True)

    def configure(self, user_id_expression):
        self._user_id_expression = user_id_expression

    def __call__(self, item, evaluation_context=None):
        user_id = self._user_id_expression(item, evaluation_context)
        if not user_id:
            return []

        assert evaluation_context.root_doc['domain']
        return self._get_groups(user_id, evaluation_context)

    @ucr_context_cache(vary_on=('user_id',))
    def _get_groups(self, user_id, evaluation_context):
        domain = evaluation_context.root_doc['domain']
        try:
            user = CommCareUser.get_by_user_id(user_id, domain)
        except CouchUser.AccountTypeError:
            user = None
        if not user:
            return []

        groups = self._get_groups_from_user(user)
        return [g.to_json() for g in groups]

    def _get_groups_from_user(self, user):
        raise NotImplementedError


class CaseSharingGroupsExpressionSpec(_GroupsExpressionSpec):
    """
    ``get_case_sharing_groups`` will return an array of the case sharing
    groups that are assigned to a provided user ID. The array will contain
    one document per case sharing group.

    .. code:: json

       {
           "type": "get_case_sharing_groups",
           "user_id_expression": {
               "type": "property_path",
               "property_path": ["form", "meta", "userID"]
           }
       }
    """
    type = TypeProperty('get_case_sharing_groups')

    def _get_groups_from_user(self, user):
        return user.get_case_sharing_groups()

    def __str__(self):
        return "get case sharing groups for {}".format(str(self._user_id_expression))


class ReportingGroupsExpressionSpec(_GroupsExpressionSpec):
    """
    ``get_reporting_groups`` will return an array of the reporting groups that
    are assigned to a provided user ID. The array will contain one document
    per reporting group.

    .. code:: json

       {
           "type": "get_reporting_groups",
           "user_id_expression": {
               "type": "property_path",
               "property_path": ["form", "meta", "userID"]
           }
       }
    """
    type = TypeProperty('get_reporting_groups')

    def _get_groups_from_user(self, user):
        return user.get_reporting_groups()

    def __str__(self):
        return "get reporting groups for {}".format(str(self._user_id_expression))


class SplitStringExpressionSpec(JsonObject):
    """
    This expression returns ``(doc["foo bar"]).split(' ')[0]``:

    .. code:: json

       {
           "type": "split_string",
           "string_expression": {
               "type": "property_name",
               "property_name": "multiple_value_string"
           },
           "index_expression": {
               "type": "constant",
               "constant": 0
           },
           "delimiter": ","
       }

    The delimiter is optional and is defaulted to a space. It will return
    nothing if the string_expression is not a string, or if the index isn't
    a number or the indexed item doesn't exist. The index_expression is also
    optional. Without it, the expression will return the list of elements.
    """
    type = TypeProperty('split_string')
    string_expression = DictProperty(required=True)
    index_expression = DefaultProperty(required=False)
    delimiter = StringProperty(required=False)

    def configure(self, string_expression, index_expression):
        self._string_expression = string_expression
        self._index_expression = index_expression

    def __call__(self, item, evaluation_context=None):
        string_value = self._string_expression(item, evaluation_context)
        if not isinstance(string_value, str):
            return None

        index_value = None
        if self.index_expression is not None:
            index_value = self._index_expression(item, evaluation_context)
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
    """
    This expression returns the value of the expression provided, or the
    value of the default_expression if the expression provided evaluates to a
    null or blank string.

    .. code:: json

       {
           "type": "coalesce",
           "expression": {
               "type": "property_name",
               "property_name": "district"
           },
           "default_expression": {
               "type": "constant",
               "constant": "default_district"
           }
       }
    """
    type = TypeProperty('coalesce')
    expression = DictProperty(required=True)
    default_expression = DictProperty(required=True)

    def configure(self, expression, default_expression):
        self._expression = expression
        self._default_expression = default_expression

    def __call__(self, item, evaluation_context=None):
        expression_value = self._expression(item, evaluation_context)
        default_value = self._default_expression(item, evaluation_context)
        if expression_value is None or expression_value == '':
            return default_value
        else:
            return expression_value

    def __str__(self):
        return "coalesce({}, {})".format(str(self._expression), str(self._default_expression))
