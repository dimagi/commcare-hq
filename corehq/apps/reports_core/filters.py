from collections import namedtuple
from datetime import datetime, time
from corehq.apps.reports_core.exceptions import FilterValueException
from corehq.apps.userreports.expressions.getters import transform_from_datatype
from corehq.apps.userreports.reports.filters.values import SHOW_ALL_CHOICE, CHOICE_DELIMITER
from corehq.apps.userreports.util import localize
from corehq.util.dates import iso_string_to_date

from dimagi.utils.dates import DateSpan
from dimagi.utils.decorators.memoized import memoized
from django.utils.translation import ugettext_lazy as _


FilterParam = namedtuple('FilterParam', ['name', 'required'])


class BaseFilter(object):
    """
    Base object for filters.
    """
    template = None
    javascript_template = None

    def __init__(self, name, params=None):
        self.name = name
        self.params = params or []

    def get_value(self, context):
        if self.check_context(context):
            kwargs = {param.name: context[param.name] for param in self.params if param.name in context}
            return self.value(**kwargs)
        else:
            return self.default_value()

    def check_context(self, context):
        return all(slug.name in context for slug in self.params if slug.required)

    def value(self, **kwargs):
        """
        Override this and return the value. This method will only be called if all required
        parameters are present in the filter context. All the parameters present in the context
        will be passed in as keyword arguments.

        If any of the parameters are invalid a FilterValueException should be raised.

        This method should generally be memoized.
        """
        return None

    def default_value(self):
        """
        If the filter is not marked as required and the user does not supply any / all necessary parameters
        this value will be used instead.
        """
        return None

    def context(self, value, lang=None):
        """
        Context for rendering the filter.
        """
        context = {
            'label': localize(self.label, lang),
            'css_id': self.css_id,
            'value': value,
        }
        context.update(self.filter_context())
        return context

    def filter_context(self):
        """
        Override to supply additional context.
        """
        return {}


class DatespanFilter(BaseFilter):
    template = 'reports_core/filters/datespan_filter/datespan_filter.html'
    javascript_template = 'reports_core/filters/datespan_filter/datespan_filter.js'

    def __init__(self, name, label='Datespan Filter',
                 css_id=None):
        self.label = label
        self.css_id = css_id or name
        params = [
            FilterParam(self.startdate_param_name, True),
            FilterParam(self.enddate_param_name, True),
            FilterParam('date_range_inclusive', False),
        ]
        super(DatespanFilter, self).__init__(name=name, params=params)

    @property
    def startdate_param_name(self):
        return '{}-start'.format(self.css_id)

    @property
    def enddate_param_name(self):
        return '{}-end'.format(self.css_id)

    @memoized
    def value(self, **kwargs):
        startdate = kwargs[self.startdate_param_name]
        enddate = kwargs[self.enddate_param_name]
        date_range_inclusive = kwargs.get('date_range_inclusive', True)

        def date_or_nothing(param):
            if param:
                return datetime.combine(iso_string_to_date(param), time())
            else:
                return None
        try:
            startdate = date_or_nothing(startdate)
            enddate = date_or_nothing(enddate)
        except (ValueError, TypeError) as e:
            raise FilterValueException('Error parsing date parameters: {}'.format(e.message))

        if startdate or enddate:
            return DateSpan(startdate, enddate, inclusive=date_range_inclusive)

    def default_value(self):
        # default to "Show All Dates"
        return None

    def filter_context(self):
        return {
            'timezone': None
        }


class NumericFilter(BaseFilter):
    template = "reports_core/filters/numeric_filter.html"

    def __init__(self, name, label=_('Numeric Filter'), css_id=None):
        self.label = label
        self.css_id = css_id or name
        params = [
            FilterParam(self.operator_param_name, True),
            FilterParam(self.operand_param_name, True),
        ]
        super(NumericFilter, self).__init__(name=name, params=params)

    @property
    def operator_param_name(self):
        return "{}-operator".format(self.css_id)

    @property
    def operand_param_name(self):
        return "{}-operand".format(self.css_id)

    @memoized
    def value(self, **kwargs):
        operator = kwargs[self.operator_param_name]
        operand = kwargs[self.operand_param_name]
        if operand == "":
            return None
        try:
            assert operator in ["=", "!=", "<", "<=", ">", ">="]
            assert isinstance(operand, float) or isinstance(operand, int)
        except AssertionError as e:
            raise FilterValueException('Error parsing numeric filter parameters: {}'.format(e.message))

        return {"operator": operator, "operand": operand}

    def default_value(self):
        return None


Choice = namedtuple('Choice', ['value', 'display'])


class ChoiceListFilter(BaseFilter):
    """
    Filter for a list of choices. Each choice should be a Choice object as per above.
    """
    template = 'reports_core/filters/choice_list_filter.html'

    def __init__(self, name, datatype, label='Choice List Filter',
                 css_id=None, choices=None):
        params = [
            FilterParam(name, True),
        ]
        super(ChoiceListFilter, self).__init__(name=name, params=params)
        self.datatype = datatype
        self.label = label
        self.css_id = css_id or self.name
        self.choices = choices or []

    def value(self, **kwargs):
        raw_value = kwargs[self.name]
        choice = transform_from_datatype(self.datatype)(raw_value) if raw_value != SHOW_ALL_CHOICE else raw_value
        choice_values = map(lambda c: c.value, self.choices)
        if choice not in choice_values:
            raise FilterValueException(_(u'Choice "{choice}" not found in choices: {choices}')
                                       .format(choice=choice,
                                               choices=choice_values))
        return next(choice_obj for choice_obj in self.choices if choice_obj.value == choice)

    def default_value(self):
        return self.choices[0]


class DynamicChoiceListFilter(BaseFilter):
    """
    Filter for a list of choices.

    The choices are generated dynamically based on the database.
    """
    template = 'reports_core/filters/dynamic_choice_list_filter/dynamic_choice_list.html'
    javascript_template = 'reports_core/filters/dynamic_choice_list_filter/dynamic_choice_list.js'

    def __init__(self, name, field, datatype, label, show_all, url_generator, choice_provider, css_id=None):
        """
        url_generator should be a callable that takes a domain, report, and filter and returns a url.
        see userreports.reports.filters.dynamic_choice_list_url for an example.
        """
        params = [
            FilterParam(name, True),
        ]
        super(DynamicChoiceListFilter, self).__init__(name=name, params=params)
        self.datatype = datatype
        self.field = field
        self.label = label
        self.show_all = show_all
        self.css_id = css_id or self.name
        self.url_generator = url_generator
        self.choice_provider = choice_provider

    def value(self, **kwargs):
        selection = unicode(kwargs.get(self.name, ""))
        if selection:
            choices = selection.split(CHOICE_DELIMITER)
            typed_choices = [transform_from_datatype(self.datatype)(c) for c in choices]
            return self.choice_provider.get_choices_for_known_values(typed_choices)
        return self.default_value()

    def default_value(self):
        return [Choice(SHOW_ALL_CHOICE, '')]
