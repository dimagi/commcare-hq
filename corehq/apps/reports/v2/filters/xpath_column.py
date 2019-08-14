from __future__ import absolute_import
from __future__ import unicode_literals

import datetime
from collections import namedtuple

import dateutil
from memoized import memoized
from django.utils.translation import ugettext_lazy

from corehq.apps.case_search.const import (
    SPECIAL_CASE_PROPERTIES,
    CASE_COMPUTED_METADATA,
)
from corehq.apps.reports.util import get_report_timezone
from corehq.apps.reports.v2.models import BaseFilter
from corehq.apps.reports.v2.exceptions import ColumnFilterNotFound


ChoiceMeta = namedtuple('ChoiceMeta', 'title name operator')
AppliedFilterContext = namedtuple(
    'AppliedFilterContext',
    'filter_name choice_name value'
)


class DataType(object):
    TEXT = 'text'
    NUMERIC = 'numeric'
    DATE = 'date'


class Clause(object):
    ALL = 'all'
    ANY = 'any'


class BaseXpathColumnFilter(BaseFilter):
    name = None
    title = None
    data_type = None
    choices = []

    def __init__(self, request, domain):
        self.request = request
        self.domain = domain

    @classmethod
    def get_context(cls):
        return {
            'title': cls.title,
            'name': cls.name,
            'type': cls.data_type,
            'choices': [
                {
                    'title': c.title,
                    'name': c.name
                } for c in cls.choices
            ],
        }

    def get_expression(self, property, choice_name, value):
        value = self.format_value(value)
        operator = self.get_operator(choice_name)
        return "{property} {operator} {value}".format(
            property=property,
            operator=operator,
            value=value,
        )

    def format_value(self, value):
        return value

    def get_operator(self, choice_name):
        name_to_operator = {c.name: c.operator for c in self.choices}
        # Let this fail hard on KeyError, as it signals an issue on the JS side
        return name_to_operator[choice_name]


class TextXpathColumnFilter(BaseXpathColumnFilter):
    title = ugettext_lazy("Text")
    name = 'xpath_column_text'
    data_type = DataType.TEXT
    choices = [
        ChoiceMeta(ugettext_lazy("Text equals"), 'text_equals', '='),
        ChoiceMeta(ugettext_lazy("Text does not equal"), 'text_not_equals', '!='),
    ]

    def format_value(self, value):
        return "'{}'".format(value)


class NumericXpathColumnFilter(BaseXpathColumnFilter):
    title = ugettext_lazy("a Number")
    name = 'xpath_column_number'
    data_type = DataType.NUMERIC
    choices = [
        ChoiceMeta(ugettext_lazy("Number is equal to"), 'num_equals', '='),
        ChoiceMeta(ugettext_lazy("Number is less than"), 'num_less_than', '<'),
        ChoiceMeta(ugettext_lazy("Number is greater than"), 'num_greater_than', '>'),
        ChoiceMeta(ugettext_lazy("Number is not equal to"), 'num_not_equals', '!='),
    ]

    @staticmethod
    def _get_number(value):
        try:
            value = int(value)
        except ValueError:
            value = float(value)

        if value < 0:
            value = "'{}'".format(value)

        return value

    def format_value(self, value):
        return "''" if value == '' else self._get_number(value)


class DateXpathColumnFilter(BaseXpathColumnFilter):
    title = ugettext_lazy("a Date")
    name = 'xpath_column_date'
    data_type = DataType.DATE
    choices = [
        ChoiceMeta(ugettext_lazy("Date is"), 'date_is', '='),
        ChoiceMeta(ugettext_lazy("Date is before"), 'date_before', '<'),
        ChoiceMeta(ugettext_lazy("Date is after"), "date_after", '>'),
    ]

    def __init__(self, request, domain):
        super(DateXpathColumnFilter, self).__init__(request, domain)
        self.adjust_to_utc = False

    @property
    @memoized
    def _timezone(self):
        return get_report_timezone(self.request, self.domain)

    def _adjust_to_utc(self, date):
        if not self.adjust_to_utc:
            # only adjust date to UTC if compared to a calculated property
            return date

        localized = self._timezone.localize(date)
        offset = localized.strftime("%z")
        return date - datetime.timedelta(
            hours=int(offset[0:3]),
            minutes=int(offset[0] + offset[3:5])
        )

    def get_expression(self, property, choice_name, value):
        server_properties = SPECIAL_CASE_PROPERTIES + CASE_COMPUTED_METADATA
        if property in server_properties:
            self.adjust_to_utc = True

        if choice_name == 'date_is':
            # This combined range has to be applied as using the '='
            # operator will treat the value as a string match
            value = self.format_value(value)
            return "{property} <= {value} and {property} >= {value}".format(
                property=property,
                value=value,
            )
        return super(DateXpathColumnFilter, self).get_expression(
            property, choice_name, value
        )

    def _format_date(self, value):
        date_object = self._adjust_to_utc(dateutil.parser.parse(value))
        return date_object.strftime("%Y-%m-%d")

    def format_value(self, value):
        return "'{}'".format(self._format_date(value))


class ColumnXpathExpressionBuilder(object):

    def __init__(self, request, domain, column_context, column_filters):
        self.request = request
        self.domain = domain
        self.column_name = column_context['name']
        self.clause = column_context.get('clause', Clause.ALL)
        self.column_filters = column_filters
        self.applied_filters = []
        for filter_context in column_context.get('filters', []):
            self.applied_filters.append(AppliedFilterContext(
                filter_name=filter_context['filterName'],
                choice_name=filter_context['choiceName'],
                value=filter_context['value'],
            ))

    def _get_filter_by_name(self, filter_name):
        name_to_class = {f.name: f for f in self.column_filters}
        try:
            column_filter = name_to_class[filter_name]
            return column_filter(self.request, self.domain)
        except (KeyError, NameError):
            raise ColumnFilterNotFound(
                "Could not find the column filter '{}'.".format(filter_name)
            )

    def get_expression(self):
        parts = []
        for context in self.applied_filters:
            column_filter = self._get_filter_by_name(context.filter_name)
            try:
                parts.append(column_filter.get_expression(
                    self.column_name,
                    context.choice_name,
                    context.value
                ))
            except ValueError:
                continue  # fail silently
        clause = " and " if self.clause == Clause.ALL else " or "
        return "({})".format(clause.join(parts)) if parts else None
