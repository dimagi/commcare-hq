from collections import namedtuple
from datetime import datetime, timedelta
from django.core.urlresolvers import reverse
from django.views.generic.base import TemplateView
from numpy import random

from braces.views import JSONResponseMixin, AjaxResponseMixin
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
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


class TestReportData(ReportDataSource):
    title = "Test Report"
    slug = "test_report"
    filters = [
        # (slug, class)
        ('datespan', DatespanFilter(required=False)),
    ]

    def slugs(self):
        return [c.data_slug for c in self.headers]

    @property
    def headers(self):
        # not sure if this belongs here
        return DataTablesHeader(
            DataTablesColumn("Date", data_slug='date'),
            DataTablesColumn("People Tested", data_slug='people_tested', sortable=False),
        )

    @property
    def total_days(self):
        return int((self.datespan.enddate - self.datespan.startdate).days)

    def daterange(self):
        p = self.config['pagination']
        days = range(self.total_days)[p.start:p.offset]

        order = self.config['ordering']
        desc = order and order[0].index == 0 and order[0].desc
        for n in days:
            if desc:
                yield self.datespan.enddate - timedelta(n)
            else:
                yield self.datespan.startdate + timedelta(n)

    def get_data(self):
        if self.datespan:
            for date in self.daterange():
                yield {
                    'date': date,
                    'people_tested': random.randint(0, 50)
                }

    def get_total_records(self):
        return self.total_days


class TestReport(JSONResponseMixin, AjaxResponseMixin, TemplateView):
    template_name = 'reports/base_template_new.html'
    data_model = TestReportData

    content_type = None

    def dispatch(self, request, domain=None, **kwargs):
        user = request.couch_user
        if self.has_permissions(domain, user):
            if 'format' in request.GET and request.GET['format'] == 'json':
                return self.get_ajax(request, domain, **kwargs)

            return super(TestReport, self).dispatch(request, domain, **kwargs)
        else:
            raise Http403()

    def has_permissions(self, domain, user):
        return True

    def get_context_data(self, **kwargs):
        # get filter context namespaced by slug
        filter_context = {}
        for name, filter in self.data_model.filters:
            filter_context[filter.css_id] = filter.context(self.filter_params[name])
        return {
            'project': self.domain,
            'report': self.data_model,
            'filter_context': filter_context,
            'url': self.reverse(self.domain),
        }

    @property
    def domain(self):
        return getattr(self.request, 'domain', None)

    @property
    @memoized
    def request_dict(self):
        params = json_request(self.request.GET)
        params['domain'] = self.domain
        return params

    @property
    @memoized
    def filter_params(self):
        request_dict = self.request_dict
        return {name: filter.get_value(request_dict)
                for name, filter in self.data_model.filters}

    def get_ajax(self, request, domain=None, **kwargs):
        try:
            params = self.filter_params
            params['ordering'] = datatables_ordering(self.request_dict)
            params['pagination'] = datatables_paging(self.request_dict)
            data = self.data_model(params)
        except FilterException as e:
            return {
                'error': e.message
            }

        self.content_type = u"application/json"
        total_records = data.get_total_records()
        return self.render_json_response({
            'data_keys': data.slugs(),
            'aaData': list(data.get_data()),
            "sEcho": self.request_dict.get('sEcho', 0),
            "iTotalRecords": total_records,
            "iTotalDisplayRecords": total_records,
        })

    def _get_initial(self, request, **kwargs):
        pass

    @classmethod
    def reverse(cls, domain):
        return reverse(cls.data_model.slug, args=[domain])

    @classmethod
    def url_pattern(cls):
        from django.conf.urls import url
        pattern = r'^{slug}$'.format(slug=cls.data_model.slug)
        return url(pattern, cls.as_view(), name=cls.data_model.slug)


OrderingSpec = namedtuple("OrderingSpec", ["index", "desc"])
PaginationSpec = namedtuple("PaginationSpec", ["start", "limit", "offset"])

def datatables_ordering(request_dict):
    try:
        i_sorting_cols = int(request_dict.get('iSortingCols', 0))
    except ValueError:
        i_sorting_cols = 0

    ordering = []
    for i in range(i_sorting_cols):
        try:
            i_sort_col = int(request_dict.get('iSortCol_%s' % i))
        except ValueError:
            i_sort_col = 0

        # sorting order
        s_sort_dir = request_dict.get('sSortDir_%s' % i)
        desc = s_sort_dir == 'desc'

        ordering.append(OrderingSpec(index=i_sort_col, desc=desc))

    return ordering

def datatables_paging(request_dict):
    limit = int(request_dict.get('iDisplayLength', 10))
    start = int(request_dict.get('iDisplayStart', 0))
    offset = start + limit

    return PaginationSpec(start=start, limit=limit, offset=offset)

