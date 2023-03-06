from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.html import format_html
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from corehq.apps.domain.decorators import domain_admin_required
from corehq.apps.domain.views import BaseProjectSettingsView
from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader
from corehq.apps.reports.dispatcher import DomainReportDispatcher
from corehq.apps.reports.filters.base import BaseMultipleOptionFilter
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import DatespanMixin
from corehq.motech.generic_inbound.models import ConfigurableAPI
from corehq.toggles import GENERIC_INBOUND_API
from corehq.util import reverse
from corehq.util.timezones.conversions import ServerTime
from corehq.util.timezones.utils import get_timezone

from .models import RequestLog


class RequestStatusFilter(BaseMultipleOptionFilter):
    slug = 'request_status'
    label = gettext_lazy('Request Status')

    @property
    def options(self):
        return RequestLog.Status.choices


class ApiFilter(BaseMultipleOptionFilter):
    slug = 'api_id'
    label = gettext_lazy('API')

    @property
    def options(self):
        api_list = [(str(api.id), api.name) for api in ConfigurableAPI.objects.filter(domain=self.domain)]
        return api_list


class ApiRequestLogReport(DatespanMixin, GenericTabularReport):
    name = gettext_lazy('Inbound API Request Logs')
    slug = 'api_request_log_report'
    base_template = "reports/base_template.html"
    section_name = gettext_lazy('Project Settings')
    dispatcher = DomainReportDispatcher
    ajax_pagination = True
    sortable = False

    fields = [
        'corehq.apps.reports.filters.dates.DatespanFilter',
        'corehq.motech.generic_inbound.reports.RequestStatusFilter',
        'corehq.motech.generic_inbound.reports.ApiFilter',
    ]

    toggles = [GENERIC_INBOUND_API]

    @classmethod
    def allow_access(cls, request):
        return request.couch_user.is_domain_admin()

    @property
    def total_records(self):
        return self._queryset.count()

    @property
    def shared_pagination_GET_params(self):
        return [
            {'name': param, 'value': self.request.GET.getlist(param)}
            for param in ['request_status', 'startdate', 'enddate', 'api_id']
        ]

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn(_("API")),
            DataTablesColumn(_("Timestamp")),
            DataTablesColumn(_("Status")),
            DataTablesColumn(_("Response")),
            DataTablesColumn(_("Details")),
        )

    @cached_property
    def _queryset(self):
        queryset = RequestLog.objects.filter(
            domain=self.domain,
            timestamp__gte=self.request.datespan.startdate_utc,
            timestamp__lt=self.request.datespan.enddate_utc,
        )
        status = self.request.GET.getlist('request_status')
        if status:
            queryset = queryset.filter(status__in=status)
        api_ids = self.request.GET.getlist('api_id')
        if api_ids:
            queryset = queryset.filter(api_id__in=api_ids)
        return queryset

    @property
    def rows(self):
        for log in self._queryset[self.pagination.start:self.pagination.end]:
            yield [
                log.api.name,
                ServerTime(log.timestamp).user_time(self.timezone).ui_string(),
                log.get_status_display(),
                log.response_status,
                _to_link(log),
            ]


def _to_link(log):
    return format_html(
        "<a href={}>{}</a>",
        reverse(ApiLogDetailView.urlname, args=[log.domain, log.id]),
        _("View Details"),
    )


@method_decorator([GENERIC_INBOUND_API.required_decorator(), domain_admin_required], name='dispatch')
class ApiLogDetailView(BaseProjectSettingsView):
    page_title = gettext_lazy("API Request Log")
    urlname = 'api_log_detail'
    template_name = 'generic_inbound/request_log_detail.html'

    @cached_property
    def log(self):
        return get_object_or_404(RequestLog, domain=self.domain, id=self.kwargs['log_id'])

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain, self.log.id])

    @property
    def page_context(self):
        return {
            'log': self.log,
            'timezone': get_timezone(self.request, self.domain)
        }
