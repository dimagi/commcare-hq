from django.core.urlresolvers import reverse
from django.views.generic.base import TemplateView
from braces.views import JSONResponseMixin
from corehq.apps.reports.dispatcher import cls_to_view_login_and_domain
from corehq.apps.userreports.exceptions import UserReportsError
from corehq.apps.userreports.models import ReportConfiguration
from corehq.apps.userreports.reports.factory import ReportFactory
from corehq.util.couch import get_document_or_404
from dimagi.utils.couch.pagination import DatatablesParams
from dimagi.utils.decorators.memoized import memoized

from dimagi.utils.web import json_request
from no_exceptions.exceptions import Http403

from corehq.apps.reports.datatables import DataTablesHeader


class ConfigurableReport(JSONResponseMixin, TemplateView):
    template_name = 'userreports/configurable_report.html'
    slug = "configurable"

    @property
    @memoized
    def spec(self):
        return get_document_or_404(ReportConfiguration, self.domain, self.report_config_id)

    @property
    def title(self):
        return self.spec.title

    @property
    @memoized
    def data_source(self):
        return ReportFactory.from_spec(self.spec)

    @property
    @memoized
    def request_dict(self):
        request_dict = json_request(self.request.GET)
        request_dict['domain'] = self.domain
        return request_dict

    @property
    @memoized
    def filter_values(self):
        return {
            filter.css_id: filter.get_value(self.request_dict)
            for filter in self.filters
        }

    @property
    @memoized
    def filter_context(self):
        return {
            filter.css_id: filter.context(self.filter_values[filter.css_id])
            for filter in self.filters
        }

    @property
    @memoized
    def filters(self):
        return self.spec.ui_filters

    @cls_to_view_login_and_domain
    def dispatch(self, request, domain, report_config_id, **kwargs):
        self.domain = domain
        self.report_config_id = report_config_id
        user = request.couch_user
        if self.has_permissions(domain, user):
            if request.is_ajax() or request.GET.get('format', None) == 'json':
                return self.get_ajax(request, domain, **kwargs)
            self.content_type = None
            return super(ConfigurableReport, self).dispatch(request, domain, **kwargs)
        else:
            raise Http403()

    def has_permissions(self, domain, user):
        return True

    def get_context_data(self, **kwargs):
        return {
            'domain': self.domain,
            'report': self,
            'filter_context': self.filter_context,
            'url': reverse(self.slug, args=[self.domain, self.report_config_id]),
            'headers': self.headers,
        }

    @property
    def headers(self):
        return DataTablesHeader(*[col.data_tables_column for col in self.data_source.columns])

    def get_ajax(self, request, domain=None, **kwargs):
        try:
            data = self.data_source
            data.set_filter_values(self.filter_values)
            total_records = data.get_total_records()
        except UserReportsError as e:
            return self.render_json_response({
                'error': e.message,
            })

        # todo: this is ghetto pagination - still doing a lot of work in the database
        datatables_params = DatatablesParams.from_request_dict(request.GET)
        end = min(datatables_params.start + datatables_params.count, total_records)
        page = list(data.get_data())[datatables_params.start:end]
        return self.render_json_response({
            'aaData': page,
            "sEcho": self.request_dict.get('sEcho', 0),
            "iTotalRecords": total_records,
            "iTotalDisplayRecords": total_records,
        })

    def _get_initial(self, request, **kwargs):
        pass

    @classmethod
    def url_pattern(cls):
        from django.conf.urls import url
        pattern = r'^{slug}/(?P<report_config_id>[\w\-:]+)/$'.format(slug=cls.slug)
        return url(pattern, cls.as_view(), name=cls.slug)
