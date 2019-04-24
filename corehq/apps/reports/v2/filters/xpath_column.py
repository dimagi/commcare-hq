from __future__ import absolute_import
from __future__ import unicode_literals
from collections import namedtuple

from django.utils.translation import ugettext_lazy

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


class Clause(object):
    ALL = 'all'
    ANY = 'any'


class BaseXpathColumnFilter(BaseFilter):
    name = None
    title = None
    data_type = None
    choices = []

    @classmethod
    def get_expression(cls, property, choice_name, value):
        value = cls.format_value(value)
        operator = cls.get_operator(choice_name)
        return "{property} {operator} {value}".format(
            property=property,
            operator=operator,
            value=value,
        )

    @classmethod
    def format_value(cls, value):
        return value

    @classmethod
    def get_operator(cls, choice_name):
        name_to_operator = {c.name: c.operator for c in cls.choices}
        # Let this fail hard on KeyError, as it signals an issue on the JS side
        return name_to_operator[choice_name]

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


class TextXpathColumnFilter(BaseXpathColumnFilter):
    title = ugettext_lazy("Text")
    name = 'xpath_column_text'
    data_type = DataType.TEXT
    choices = [
        ChoiceMeta(ugettext_lazy("Equals"), 'text_equals', '='),
        ChoiceMeta(ugettext_lazy("Does not equal"), 'text_not_equals', '!='),
    ]

    @classmethod
    def format_value(cls, value):
        return "'{}'".format(value)


class NumericXpathColumnFilter(BaseXpathColumnFilter):
    title = ugettext_lazy("Number")
    name = 'xpath_column_number'
    data_type = DataType.NUMERIC
    choices = [
        ChoiceMeta(ugettext_lazy("Is equal to"), 'num_equals', '='),
        ChoiceMeta(ugettext_lazy("Is less than"), 'num_less_than', '<'),
        ChoiceMeta(ugettext_lazy("Is greater than"), 'num_greater_than', '>'),
        ChoiceMeta(ugettext_lazy("Is not equal to"), 'num_not_equals', '!='),
    ]

    @staticmethod
    def _get_number(value):
        try:
            return int(value)
        except ValueError:
            return float(value)

    @classmethod
    def format_value(cls, value):
        return "'{}'".format(value) if value == '' else cls._get_number(value)


class ColumnXpathExpressionBuilder(object):

    def __init__(self, column_context, column_filters):
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
            return column_filter
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
