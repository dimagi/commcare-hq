from collections import namedtuple
from datetime import datetime

from dimagi.utils.dates import DateSpan
from dimagi.utils.decorators.memoized import memoized


class FilterException(Exception):
    pass


class MissingParamException(FilterException):
    pass


class FilterValueException(FilterException):
    pass


FilterParam = namedtuple('FilterParam', ['name', 'required'])


class BaseFilter(object):
    """
    Base object for filters. These objects deal with data only are not concerned with being
    rendered on a view.

    :params: A list of FilterParams which are used by this filter.
    """
    params = []

    def __init__(self, required=False):
        self.required = required

    def get_value(self, context):
        from pprint import pprint
        pprint(context)
        context_ok = self.check_context(context)
        if self.required and not context_ok:
            required_slugs = ', '.join([slug.name for slug in self.params if slug.required])
            raise MissingParamException("Missing filter parameters. "
                                        "Required parameters are: {}".format(required_slugs))

        if context_ok:
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
        If the filter is not required this value will be used if self.value returns None
        """
        return None

    def context(self, value):
        context = {
            'label': self.label,
            'css_id': self.css_id,
            'value': value,
        }
        context.update(self.filter_context())
        return context

    def filter_context(self):
        return {}


class DatespanFilter(BaseFilter):
    label = "Datespan Filter"
    template = "reports/filter_new.html"
    css_id = 'datespan'
    params = [
        FilterParam('startdate', True),
        FilterParam('enddate', True),
        FilterParam('date_range_inclusive', False),
    ]

    @memoized
    def value(self, startdate, enddate, date_range_inclusive=True):
        def date_or_nothing(param):
            return datetime.strptime(param, "%Y-%m-%d") \
                if param else None
        try:
            startdate = date_or_nothing(startdate)
            enddate = date_or_nothing(enddate)
        except (ValueError, TypeError) as e:
            raise FilterValueException('Error parsing date parameters: {}'.format(e.message))

        if startdate or enddate:
            return DateSpan(startdate, enddate, inclusive=date_range_inclusive)

    def default_value(self):
        return DateSpan.since(7)

    def filter_context(self):
        return {
            'timezone': None
        }
