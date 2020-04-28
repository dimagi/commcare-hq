from datetime import datetime

from django.contrib import messages
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy
from django.views.decorators.http import require_GET

from corehq import toggles
from corehq.apps.hqwebapp.utils import get_bulk_upload_form
from corehq.apps.locations.models import LocationType, SQLLocation
from corehq.apps.locations.permissions import require_can_edit_locations
from corehq.apps.locations.views import BaseLocationView, LocationsListView
from corehq.const import FILENAME_DATETIME_FORMAT
from corehq.util.files import safe_filename_header
from corehq.util.workbook_json.excel import WorkbookJSONError, get_workbook
from custom.icds.location_reassignment.const import AWC_CODE
from custom.icds.location_reassignment.download import Download
from custom.icds.location_reassignment.dumper import Dumper
from custom.icds.location_reassignment.forms import (
    LocationReassignmentRequestForm,
)
from custom.icds.location_reassignment.parser import (
    HouseholdReassignmentParser,
    Parser,
)
from custom.icds.location_reassignment.tasks import (
    email_household_details,
    process_households_reassignment,
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
                "plural_noun": _("location reassignments"),
                "verb": _("Perform"),
                "help_link": "https://confluence.dimagi.com/display/ICDS/Location+Reassignment",
            },
        })
        context.update({
            'bulk_upload_form': get_bulk_upload_form(context, form_class=LocationReassignmentRequestForm),
        })
        return context

    def post(self, request, *args, **kwargs):
        uploaded_file = request.FILES['bulk_upload_file']
        workbook, errors = self._get_workbook(uploaded_file)
        if errors:
            [messages.error(request, error) for error in errors]
            return self.get(request, *args, **kwargs)
        action_type = request.POST.get('action_type')
        parser = self._get_parser(action_type, workbook)
        errors = parser.parse()
        if errors:
            [messages.error(request, error) for error in errors]
        else:
            if action_type == LocationReassignmentRequestForm.EMAIL_HOUSEHOLDS:
                self._process_request_for_email_households(parser, request)
            elif action_type == LocationReassignmentRequestForm.UPDATE:
                self._process_request_for_update(parser, request)
            elif action_type == LocationReassignmentRequestForm.REASSIGN_HOUSEHOLDS:
                self._process_request_for_household_reassignment(parser, request)
            else:
                return self._generate_summary_response(parser.valid_transitions, uploaded_file.name)
        return self.get(request, *args, **kwargs)

    def _get_parser(self, action_type, workbook):
        if action_type == LocationReassignmentRequestForm.REASSIGN_HOUSEHOLDS:
            return HouseholdReassignmentParser(self.domain, workbook)
        return Parser(self.domain, workbook)

    def _get_workbook(self, uploaded_file):
        try:
            workbook = get_workbook(uploaded_file)
        except WorkbookJSONError as e:
            return None, [str(e)]
        return workbook, self._workbook_is_valid(workbook)

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

    def _generate_summary_response(self, transitions, uploaded_filename):
        filename = uploaded_filename.split('.')[0] + " Summary"
        response_file = Dumper(self.domain).dump(transitions)
        response = HttpResponse(response_file, content_type="text/html; charset=utf-8")
        response['Content-Disposition'] = safe_filename_header(filename, 'xlsx')
        return response

    def _process_request_for_email_households(self, parser, request):
        if AWC_CODE in parser.valid_transitions:
            email_household_details.delay(self.domain, parser.valid_transitions[AWC_CODE],
                                          request.user.email)
            messages.success(request, _(
                "Your request has been submitted. You will be updated via email."))
        else:
            messages.error(request, "No transitions found for %s" % AWC_CODE)

    def _process_request_for_update(self, parser, request):
        process_location_reassignment.delay(
            self.domain, parser.valid_transitions_json(),
            request.user.email
        )
        messages.success(request, _(
            "Your request has been submitted. We will notify you via email once completed."))

    def _process_request_for_household_reassignment(self, parser, request):
        process_households_reassignment.delay(
            self.domain, parser.reassignments, request.user.email
        )
        messages.success(request, _(
            "Your request has been submitted. We will notify you via email once completed."))


@toggles.LOCATION_REASSIGNMENT.required_decorator()
@require_can_edit_locations
@require_GET
def download_location_reassignment_template(request, domain):
    location_id = request.GET.get('location_id')

    if not location_id:
        messages.error(request, _("Please select a location."))
        return HttpResponseRedirect(reverse(LocationReassignmentView.urlname, args=[domain]))

    location = SQLLocation.active_objects.get(location_id=location_id, domain=domain)
    response_file = Download(location).dump()
    response = HttpResponse(response_file, content_type="text/html; charset=utf-8")
    creation_time = datetime.utcnow().strftime(FILENAME_DATETIME_FORMAT)
    filename = f"[{domain}] {location.name} Location Reassignment Request Template {creation_time}"
    response['Content-Disposition'] = safe_filename_header(filename, 'xlsx')
    return response
