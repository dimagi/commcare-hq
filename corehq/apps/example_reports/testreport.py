from collections import namedtuple
from datetime import timedelta
from numpy import random

from django.core.urlresolvers import reverse
from django.views.generic.base import TemplateView
from braces.views import JSONResponseMixin
from corehq.apps.reports_core.exceptions import FilterException

from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.web import json_request
from no_exceptions.exceptions import Http403

from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.api import ReportDataSource
from corehq.apps.reports_core.filters import DatespanFilter


Column = namedtuple("Column", ["slug", "display_name", "sortable"])


class TestReportData(ReportDataSource):
    title = "Test Report"
    slug = "test_report"
    filters = [
        DatespanFilter(name='datespan', required=False),
    ]

    def columns(self):
        return [
            Column(slug="date", display_name="Date", sortable=True),
            Column(slug="people_tested", display_name="People Tested", sortable=False),
        ]

    @property
    def total_days(self):
        return int((self.config['datespan'].enddate - self.config['datespan'].startdate).days)

    def daterange(self):
        p = self.config['pagination']
        days = range(self.total_days)[p.start:p.offset]

        order = self.config['ordering'].get('date', None)
        desc = order and order.desc
        for n in days:
            if desc:
                yield self.config['datespan'].enddate - timedelta(n)
            else:
                yield self.config['datespan'].startdate + timedelta(n)

    def get_data(self):
        # replace this with a generic has_parameter method
        if hasattr(self, 'datespan'):
            for date in self.daterange():
                yield {
                    'date': date,
                    'people_tested': random.randint(0, 50)
                }

    def get_total_records(self):
        return self.total_days


class TestReport(JSONResponseMixin, TemplateView):
    template_name = 'reports_core/base_template_new.html'
    data_model = TestReportData

    def dispatch(self, request, domain=None, **kwargs):
        user = request.couch_user
        if self.has_permissions(domain, user):
            if request.is_ajax() or request.GET.get('format', None) == 'json':
                return self.get_ajax(request, domain, **kwargs)
            self.content_type = None
            return super(TestReport, self).dispatch(request, domain, **kwargs)
        else:
            raise Http403()

    def has_permissions(self, domain, user):
        return True

    def get_context_data(self, **kwargs):
        # get filter context namespaced by slug
        filter_context = {}
        for filter in self.data_model.filters:
            filter_context[filter.name] = filter.context(self.filter_params[filter.css_id])
        return {
            'project': self.domain,
            'report': self.data_model,
            'filter_context': filter_context,
            'url': self.reverse(self.domain),
            'headers': self.headers,
        }

    @property
    def headers(self):
        data = self.data_model()

        def make_column(col):
            return DataTablesColumn(col.display_name, data_slug=col.slug, sortable=col.sortable)

        columns = map(make_column, data.columns())
        return DataTablesHeader(*columns)

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
        return {
            filter.name: filter.get_value(request_dict)
            for filter in self.data_model.filters
        }

    def get_ajax(self, request, domain=None, **kwargs):
        try:
            data = self.data_model()
            params = self.filter_params
            params['ordering'] = datatables_ordering(self.request_dict, data.columns())
            params['pagination'] = datatables_paging(self.request_dict)
            data.configure(params)
        except FilterException as e:
            return {
                'error': e.message
            }

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

        pattern = r'^{slug}/$'.format(slug=cls.data_model.slug)
        return url(pattern, cls.as_view(), name=cls.data_model.slug)


OrderedColumn = namedtuple("OrderedColumn", ["slug", "desc"])
PaginationSpec = namedtuple("PaginationSpec", ["start", "limit", "offset"])


def datatables_ordering(request_dict, columns):
    try:
        i_sorting_cols = int(request_dict.get('iSortingCols', 0))
    except ValueError:
        i_sorting_cols = 0

    ordering = {}
    for i in range(i_sorting_cols):
        try:
            i_sort_col = int(request_dict.get('iSortCol_%s' % i))
        except ValueError:
            i_sort_col = 0

        # sorting order
        s_sort_dir = request_dict.get('sSortDir_%s' % i)
        desc = s_sort_dir == 'desc'

        slug = columns[i_sort_col].slug
        ordering[slug] = OrderedColumn(slug, desc=desc)

    return ordering


def datatables_paging(request_dict):
    limit = int(request_dict.get('iDisplayLength', 10))
    start = int(request_dict.get('iDisplayStart', 0))
    offset = start + limit

    return PaginationSpec(start=start, limit=limit, offset=offset)
