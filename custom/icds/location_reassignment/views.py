from django.contrib import messages
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy
from django.views.decorators.http import require_GET

from corehq import toggles
from corehq.apps.hqwebapp.utils import get_bulk_upload_form
from corehq.apps.locations.models import LocationType
from corehq.apps.locations.permissions import require_can_edit_locations
from corehq.apps.locations.views import BaseLocationView, LocationsListView
from corehq.util.files import safe_filename_header
from corehq.util.workbook_json.excel import WorkbookJSONError, get_workbook
from custom.icds.location_reassignment.download import Download
from custom.icds.location_reassignment.dumper import Dumper
from custom.icds.location_reassignment.forms import (
    LocationReassignmentRequestForm,
)
from custom.icds.location_reassignment.parser import Parser
from custom.icds.location_reassignment.tasks import (
    process_location_reassignment,
)


@method_decorator([toggles.LOCATION_REASSIGNMENT.required_decorator()], name='dispatch')
@method_decorator(require_can_edit_locations, name='dispatch')
class LocationReassignmentView(BaseLocationView):
    section_name = ugettext_lazy("Locations")

    page_title = ugettext_lazy('Location Reassignment')
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
                "help_link": "https://confluence.dimagi.com/display/ICDS/Location+Reassignment",
            },
        })
        context.update({
            'bulk_upload_form': get_bulk_upload_form(context, form_class=LocationReassignmentRequestForm),
        })
        return context

    def post(self, request, *args, **kwargs):
        update = request.POST.get('update')
        try:
            workbook = get_workbook(request.FILES['bulk_upload_file'])
        except WorkbookJSONError as e:
            messages.error(request, str(e))
        else:
            errors = self._workbook_is_valid(workbook)
            if not errors:
                parser = Parser(self.domain, workbook)
                transitions, errors = parser.parse()
                if errors:
                    [messages.error(request, error) for error in errors]
                elif not update:
                    return self._generate_response(transitions)
                else:
                    process_location_reassignment.delay(
                        self.domain, parser.valid_transitions, parser.new_location_details,
                        list(parser.requested_transitions.keys()), request.user.email
                    )
                    messages.success(request, _(
                        "Your request has been submitted. We will notify you via email once completed."))
            else:
                [messages.error(request, error) for error in errors]
        return self.get(request, *args, **kwargs)

    def _workbook_is_valid(self, workbook):
        # ensure worksheets present and with titles as the location type codes
        errors = []
        if not workbook.worksheets:
            errors.append(_("No worksheets in workbook"))
            return errors
        worksheet_titles = [ws.title for ws in workbook.worksheets]
        location_type_codes = [lt.code for lt in LocationType.objects.by_domain(self.domain)]
        for worksheet_title in worksheet_titles:
            if worksheet_title not in location_type_codes:
                errors.append(_("Unexpected sheet {sheet_title}").format(sheet_title=worksheet_title))
        return errors

    def _generate_response(self, transitions):
        response_file = Dumper(self.domain).dump(transitions)
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

    response_file = Download(domain, location_id).dump()
    response = HttpResponse(response_file, content_type="text/html; charset=utf-8")
    filename = '%s Location Reassignment Request Template' % domain
    response['Content-Disposition'] = safe_filename_header(filename, 'xlsx')
    return response
