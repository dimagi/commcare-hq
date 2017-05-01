from jsonobject import DefaultProperty, BooleanProperty
from jsonobject.properties import ListProperty, StringProperty

from corehq.apps.userreports.expressions.factory import ExpressionFactory
from corehq.apps.userreports.specs import TypeProperty
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from dimagi.ext.jsonobject import JsonObject
from dimagi.utils.dates import force_to_datetime


class FirstCaseFormWithXmlns(JsonObject):
    type = TypeProperty('first_case_form_with_xmlns')
    xmlns = StringProperty(required=True)
    case_id_expression = DefaultProperty(required=True)
    reverse = BooleanProperty(default=False)

    def configure(self, case_id_expression):
        self._case_id_expression = case_id_expression

    def __call__(self, item, context=None):
        case_id = self._case_id_expression(item, context)

        if not case_id:
            return None

        assert context.root_doc['domain']
        return self._get_forms(case_id, context)

    def _get_forms(self, case_id, context):
        domain = context.root_doc['domain']

        cache_key = (self.__class__.__name__, case_id, self.xmlns, self.reverse)
        if context.get_cache_value(cache_key) is not None:
            return context.get_cache_value(cache_key)

        xforms = FormProcessorInterface(domain).get_case_forms(case_id)
        xforms = sorted(
            [form for form in xforms if form.xmlns == self.xmlns and form.domain == domain],
            key=lambda x: x.received_on
        )
        if not xforms:
            form = None
        else:
            index = -1 if self.reverse else 0
            form = xforms[index].to_json()

        context.set_cache_value(cache_key, form)
        return form


def first_case_form_with_xmlns_expression(spec, context):
    wrapped = FirstCaseFormWithXmlns.wrap(spec)
    wrapped.configure(
        ExpressionFactory.from_spec(wrapped.case_id_expression, context)
    )
    return wrapped


class CountCaseFormsWithXmlns(JsonObject):
    type = TypeProperty('count_case_forms_with_xmlns')
    xmlns = StringProperty(required=True)
    case_id_expression = DefaultProperty(required=True)

    def configure(self, case_id_expression):
        self._case_id_expression = case_id_expression

    def __call__(self, item, context=None):
        case_id = self._case_id_expression(item, context)

        if not case_id:
            return None

        assert context.root_doc['domain']
        return self._count_forms(case_id, context)

    def _count_forms(self, case_id, context):
        domain = context.root_doc['domain']

        cache_key = (self.__class__.__name__, case_id, self.xmlns)
        if context.get_cache_value(cache_key) is not None:
            return context.get_cache_value(cache_key)

        xforms = FormProcessorInterface(domain).get_case_forms(case_id)
        count = len([form for form in xforms if form.xmlns == self.xmlns and form.domain == domain])
        context.set_cache_value(cache_key, count)
        return count


def count_case_forms_with_xmlns_expression(spec, context):
    wrapped = CountCaseFormsWithXmlns.wrap(spec)
    wrapped.configure(
        ExpressionFactory.from_spec(wrapped.case_id_expression, context)
    )
    return wrapped


class ConcatenateStrings(JsonObject):
    type = TypeProperty('concatenate_strings')
    expressions = ListProperty(required=True)
    separator = StringProperty(required=True)

    def configure(self, expressions):
        self._expression_fns = expressions

    def __call__(self, item, context=None):
        return self.separator.join(
            [
                unicode(expression(item, context)) for expression in self._expression_fns
                if expression(item, context) is not None
            ]
        )


def concatenate_strings_expression(spec, context):
    wrapped = ConcatenateStrings.wrap(spec)
    wrapped.configure(
        [ExpressionFactory.from_spec(e, context) for e in wrapped.expressions],
    )
    return wrapped


class MonthExpression(JsonObject):
    type = TypeProperty('month_expression')
    month_expression = DefaultProperty(required=True)

    def configure(self, month_expression):
        self._month_expression = month_expression

    def __call__(self, item, context=None):
        try:
            date = force_to_datetime(self._month_expression(item, context))
        except ValueError:
            return ''
        if not date:
            return ''
        return str(date.month)


def month_expression(spec, context):
    wrapped = MonthExpression.wrap(spec)
    wrapped.configure(
        ExpressionFactory.from_spec(wrapped.month_expression, context)
    )
    return wrapped
