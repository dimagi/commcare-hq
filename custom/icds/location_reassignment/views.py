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
from custom.icds.location_reassignment.download import Download
from custom.icds.location_reassignment.dumper import Dumper
from custom.icds.location_reassignment.parser import Parser


@method_decorator([toggles.LOCATION_REASSIGNMENT.required_decorator()], name='dispatch')
@method_decorator(require_can_edit_locations, name='dispatch')
class LocationReassignmentView(BaseDomainView):
    section_name = ugettext_lazy("Locations")

    page_title = _('Location Reassignment')
    urlname = 'location_reassignment'
    template_name = 'icds/location_reassignment.html'

    def section_url(self):
        return reverse(LocationsListView.urlname, args=[self.domain])

    @property
    def page_context(self):
        context = super().page_context
        context.update({
            'bulk_upload': {
                "download_url": reverse('download_location_reassignment_template', args=[self.domain]),
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
            errors = self._workbook_is_valid(workbook)
            if not errors:
                transitions, errors = Parser(workbook.worksheets[0], self._location_types).parse()
                [messages.error(request, error) for error in errors]
                if not errors:
                    return self._generate_response(transitions)
            else:
                [messages.error(request, error) for error in errors]
        return self.get(request, *args, **kwargs)

    def _workbook_is_valid(self, workbook):
        # ToDo: Add necessary checks for workbook
        return []

    @cached_property
    def _location_types(self):
        location_types = LocationType.objects.by_domain(self.domain)
        location_types.reverse()
        return location_types

    def _generate_response(self, transitions):
        response_file = Dumper(self._location_types).dump(transitions)
        response_file.seek(0)
        response = HttpResponse(response_file, content_type="text/html; charset=utf-8")
        filename = '%s Location Reassignment Expected' % self.domain
        response['Content-Disposition'] = safe_filename_header(filename, 'xlsx')
        return response


@toggles.LOCATION_REASSIGNMENT.required_decorator()
@require_can_edit_locations
@require_GET
def download_location_reassignment_template(request, domain):
    location_id = request.GET.get('location_id')

    if not location_id:
        messages.error(request, _("Please select a location."))
        return HttpResponseRedirect(reverse(LocationReassignmentView.urlname, args=[domain]))

    response_file = Download(location_id).dump()
    response_file.seek(0)
    response = HttpResponse(response_file, content_type="text/html; charset=utf-8")
    filename = '%s Location Reassignment Request Template' % domain
    response['Content-Disposition'] = safe_filename_header(filename, 'xlsx')
    return response
