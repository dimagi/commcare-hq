from django.contrib import messages
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy
from django.views.decorators.http import require_GET

from corehq import toggles
from corehq.apps.domain.views.base import BaseDomainView
from corehq.apps.hqwebapp.utils import get_bulk_upload_form
from corehq.apps.locations.models import LocationType
from corehq.apps.locations.permissions import require_can_edit_locations
from corehq.apps.locations.views import LocationsListView
from corehq.util.files import safe_filename_header
from corehq.util.workbook_json.excel import WorkbookJSONError, get_workbook
from custom.icds.location_rationalization.download import (
    RequestTemplateDownload,
)
from custom.icds.location_rationalization.dumper import Dumper
from custom.icds.location_rationalization.parser import Parser


@method_decorator([toggles.LOCATION_RATIONALIZATION.required_decorator()], name='dispatch')
@method_decorator(require_can_edit_locations, name='dispatch')
class LocationRationalizationView(BaseDomainView):
    section_name = ugettext_lazy("Locations")

    page_title = _('Location Rationalization')
    urlname = 'location_rationalization'
    template_name = 'icds/location_rationalization.html'

    def section_url(self):
        return reverse(LocationsListView.urlname, args=[self.domain])

    @property
    def page_context(self):
        context = super().page_context
        context.update({
            'bulk_upload': {
                "download_url": reverse('download_location_rationalization', args=[self.domain]),
                "adjective": _("locations"),
                "plural_noun": _("location operations"),
                "help_link": "TODO",
            },
        })
        context.update({
            'bulk_upload_form': get_bulk_upload_form(context),
            'loc_types': self._location_types,
        })
        return context

    def post(self, request, *args, **kwargs):
        try:
            workbook = get_workbook(request.FILES['bulk_upload_file'])
        except WorkbookJSONError as e:
            messages.error(request, str(e))
        else:
            if self._workbook_is_valid(request, workbook):
                transitions, errors = Parser(workbook.worksheets[0], self._location_types).parse()
                [messages.error(request, error) for error in errors]
                if not errors:
                    return self._generate_response(transitions)
        return self.get(request, *args, **kwargs)

    def _workbook_is_valid(self, request, workbook):
        # ensure mandatory columns in the excel sheet
        worksheet = workbook.worksheets[0]
        headers = worksheet.fieldnames
        expected_headers = []
        for location_type in self._location_types:
            expected_headers.extend([f'old_{location_type}', f'new_{location_type}'])
        missing_headers = set(expected_headers) - set(headers)
        if missing_headers:
            messages.error(request, _("Missing following columns in sheet: {columns}").format(
                columns=", ".join(missing_headers)
            ))
            return False
        return True

    @cached_property
    def _location_types(self):
        location_types = [lt.code for lt in LocationType.objects.by_domain(self.domain)]
        location_types.reverse()
        return location_types

    def _generate_response(self, transitions):
        response_file = Dumper(self._location_types).dump(transitions)
        response_file.seek(0)
        response = HttpResponse(response_file, content_type="text/html; charset=utf-8")
        filename = '%s Location Rationalization - Processed' % self.domain
        response['Content-Disposition'] = safe_filename_header(filename, 'xlsx')
        return response


@toggles.LOCATION_RATIONALIZATION.required_decorator()
@require_can_edit_locations
@require_GET
def download_location_rationalization(request, domain):
    location_type = request.GET.get('location_type')
    location_id = request.GET.get('location_id')

    if not location_type or not location_id:
        messages.error(request, _("Please select a location  and a location type."))
        return HttpResponseRedirect(reverse(LocationRationalizationView.urlname, args=[domain]))

    response_file = RequestTemplateDownload(domain, location_id, location_type).dump()
    response_file.seek(0)
    response = HttpResponse(response_file, content_type="text/html; charset=utf-8")
    filename = '%s Location Rationalization Request Template' % domain
    response['Content-Disposition'] = safe_filename_header(filename, 'xlsx')
    return response
