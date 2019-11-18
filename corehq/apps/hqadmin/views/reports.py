import csv
from collections import defaultdict

from django.contrib import messages
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy

from dimagi.utils.dates import add_months
from dimagi.utils.django.management import export_as_csv_action
from dimagi.utils.web import json_response

from corehq.apps.data_analytics.admin import MALTRowAdmin
from corehq.apps.data_analytics.const import GIR_FIELDS
from corehq.apps.data_analytics.models import GIRRow, MALTRow
from corehq.apps.domain.decorators import require_superuser
from corehq.apps.es import filters
from corehq.apps.es.domains import DomainES
from corehq.apps.hqadmin.views.utils import BaseAdminSectionView


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
