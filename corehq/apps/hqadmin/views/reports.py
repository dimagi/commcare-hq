from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals

import json
from collections import defaultdict
from datetime import timedelta

import csv342 as csv
import six
import six.moves.html_parser
from django.contrib import messages
from django.http import (
    HttpResponse,
    HttpResponseBadRequest,
)
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _, ugettext_lazy
from django.views.generic import TemplateView

from corehq.apps.data_analytics.admin import MALTRowAdmin
from corehq.apps.data_analytics.const import GIR_FIELDS
from corehq.apps.data_analytics.models import MALTRow, GIRRow
from corehq.apps.domain.decorators import (
    require_superuser)
from corehq.apps.es import filters
from corehq.apps.es.domains import DomainES
from corehq.apps.hqadmin.reporting.exceptions import HistoTypeNotFoundException
from corehq.apps.hqadmin.reporting.reports import get_project_spaces, get_stats_data, HISTO_TYPE_TO_FUNC
from corehq.apps.hqadmin.views.utils import BaseAdminSectionView
from corehq.elastic import parse_args_for_es
from dimagi.utils.dates import add_months
from dimagi.utils.decorators.datespan import datespan_in_request
from dimagi.utils.django.management import export_as_csv_action
from dimagi.utils.web import json_response


@require_superuser
@datespan_in_request(from_param="startdate", to_param="enddate", default_days=90)
def stats_data(request):
    histo_type = request.GET.get('histogram_type')
    interval = request.GET.get("interval", "week")
    datefield = request.GET.get("datefield")
    get_request_params_json = request.GET.get("get_request_params", None)
    get_request_params = (
        json.loads(six.moves.html_parser.HTMLParser().unescape(get_request_params_json))
        if get_request_params_json is not None else {}
    )

    stats_kwargs = {
        k: get_request_params[k]
        for k in get_request_params if k != "domain_params_es"
    }
    if datefield is not None:
        stats_kwargs['datefield'] = datefield

    domain_params_es = get_request_params.get("domain_params_es", {})

    if not request.GET.get("enddate"):  # datespan should include up to the current day when unspecified
        request.datespan.enddate += timedelta(days=1)

    domain_params, __ = parse_args_for_es(request, prefix='es_')
    domain_params.update(domain_params_es)

    domains = get_project_spaces(facets=domain_params)

    try:
        return json_response(get_stats_data(
            histo_type,
            domains,
            request.datespan,
            interval,
            **stats_kwargs
        ))
    except HistoTypeNotFoundException:
        return HttpResponseBadRequest(
            'histogram_type param must be one of <ul><li>{}</li></ul>'
            .format('</li><li>'.join(HISTO_TYPE_TO_FUNC)))


@require_superuser
@datespan_in_request(from_param="startdate", to_param="enddate", default_days=365)
def admin_reports_stats_data(request):
    return stats_data(request)


class DimagisphereView(TemplateView):

    def get_context_data(self, **kwargs):
        context = super(DimagisphereView, self).get_context_data(**kwargs)
        context['tvmode'] = 'tvmode' in self.request.GET
        return context


def top_five_projects_by_country(request):
    data = {}
    internalMode = request.user.is_superuser
    attributes = ['internal.area', 'internal.sub_area', 'cp_n_active_cc_users', 'deployment.countries']

    if internalMode:
        attributes = ['name', 'internal.organization_name', 'internal.notes'] + attributes

    if 'country' in request.GET:
        country = request.GET.get('country')
        projects = (DomainES().is_active_project().real_domains()
                    .filter(filters.term('deployment.countries', country))
                    .sort('cp_n_active_cc_users', True).source(attributes).size(5).run().hits)
        data = {country: projects, 'internal': internalMode}

    return json_response(data)


class DownloadMALTView(BaseAdminSectionView):
    urlname = 'download_malt'
    page_title = ugettext_lazy("Download MALT")
    template_name = "hqadmin/malt_downloader.html"

    @method_decorator(require_superuser)
    def dispatch(self, request, *args, **kwargs):
        return super(DownloadMALTView, self).dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        from django.core.exceptions import ValidationError
        if 'year_month' in request.GET:
            try:
                year, month = request.GET['year_month'].split('-')
                year, month = int(year), int(month)
                return _malt_csv_response(month, year)
            except (ValueError, ValidationError):
                messages.error(
                    request,
                    _("Enter a valid year-month. e.g. 2015-09 (for September 2015)")
                )
        return super(DownloadMALTView, self).get(request, *args, **kwargs)


def _malt_csv_response(month, year):
    query_month = "{year}-{month}-01".format(year=year, month=month)
    queryset = MALTRow.objects.filter(month=query_month)
    return export_as_csv_action(exclude=['id'])(MALTRowAdmin, None, queryset)


class DownloadGIRView(BaseAdminSectionView):
    urlname = 'download_gir'
    page_title = ugettext_lazy("Download GIR")
    template_name = "hqadmin/gir_downloader.html"

    @method_decorator(require_superuser)
    def dispatch(self, request, *args, **kwargs):
        return super(DownloadGIRView, self).dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        from django.core.exceptions import ValidationError
        if 'year_month' in request.GET:
            try:
                year, month = request.GET['year_month'].split('-')
                year, month = int(year), int(month)
                return _gir_csv_response(month, year)
            except (ValueError, ValidationError):
                messages.error(
                    request,
                    _("Enter a valid year-month. e.g. 2015-09 (for September 2015)")
                )
        return super(DownloadGIRView, self).get(request, *args, **kwargs)


def _gir_csv_response(month, year):
    query_month = "{year}-{month}-01".format(year=year, month=month)
    prev_month_year, prev_month = add_months(year, month, -1)
    prev_month_string = "{year}-{month}-01".format(year=prev_month_year, month=prev_month)
    two_ago_year, two_ago_month = add_months(year, month, -2)
    two_ago_string = "{year}-{month}-01".format(year=two_ago_year, month=two_ago_month)
    if not GIRRow.objects.filter(month=query_month).exists():
        return HttpResponse('Sorry, that month is not yet available')
    queryset = GIRRow.objects.filter(month__in=[query_month, prev_month_string, two_ago_string]).order_by('-month')
    domain_months = defaultdict(list)
    for item in queryset:
        domain_months[item.domain_name].append(item)
    field_names = GIR_FIELDS
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename=gir.csv'
    writer = csv.writer(response)
    writer.writerow(list(field_names))
    for months in domain_months.values():
        writer.writerow(months[0].export_row(months[1:]))
    return response
