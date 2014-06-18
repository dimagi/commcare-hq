from collections import namedtuple
from datetime import datetime, timedelta
from django.shortcuts import render
from django.views.generic.base import TemplateView
from numpy import random
from django.views.generic import View

from braces.views import JSONResponseMixin, AjaxResponseMixin
from dimagi.utils.dates import DateSpan

from .api import ReportDataSource
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.web import json_request
from no_exceptions.exceptions import Http403


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

    def context(self, config):
        return {
            'label': self.label,
            'css_id': self.css_id,
            'value': self.get_value(config),
            'timezone': None
        }


class TestReportData(ReportDataSource):
    title = "Test Report"
    filters = [
        # (slug, class)
        ('datespan', DatespanFilter(required=False)),
    ]

    def slugs(self):
        return [
            'date',
            'people_tested'
        ]

    def daterange(self):
        for n in range(int((self.datespan.enddate - self.datespan.startdate).days)):
            yield self.datespan.startdate + timedelta(n)

    def get_data(self):
        if self.datespan:
            for date in self.daterange():
                yield {
                    'date': date,
                    'people_tested': random.randint(0, 50)
                }


class TestReport(JSONResponseMixin, AjaxResponseMixin, TemplateView):
    template_name = 'reports/base_template_new.html'
    data_model = TestReportData

    def dispatch(self, request, domain=None, **kwargs):
        user = request.couch_user
        if self.has_permissions(domain, user):
            if 'format' in request.GET and request.GET['format'] == 'json':
                return self.get_ajax(request, domain, **kwargs)

            # hack to override the content type set in JSONResponseMixin
            self.content_type = None
            return super(TestReport, self).dispatch(request, domain, **kwargs)
        else:
            raise Http403()

    def has_permissions(self, domain, user):
        return True

    def get_context_data(self, **kwargs):
        # get filter context namespaced by slug
        filter_context = {}
        for _, filter in self.data_model.filters:
            filter_context[filter.css_id] = filter.context(self.filter_params)
        return {
            'project': self.filter_params.get('domain', None),
            'report': self.data_model,
            'filter_context': filter_context,
        }

    @property
    # @memoized
    def filter_params(self):
        params = json_request(self.request.GET)
        params['domain'] = getattr(self.request, 'domain', None)
        return params

    def get_ajax(self, request, domain=None, **kwargs):
        try:
            data = self.data_model(self.filter_params)
        except FilterException as e:
            return {
                'error': e.message
            }

        return self.render_json_response({
            'data_keys': data.slugs(),
            'data': list(data.get_data())
        })

    def _get_initial(self, request, **kwargs):
        pass

    def reverse(self, params):
        return "#"
