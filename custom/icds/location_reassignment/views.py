from datetime import datetime

from django.contrib import messages
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy
from django.views.decorators.http import require_GET

from corehq import toggles
from corehq.apps.hqwebapp.utils import get_bulk_upload_form
from corehq.apps.locations.models import LocationType, SQLLocation
from corehq.apps.locations.permissions import (
    location_safe,
    require_can_edit_locations,
    user_can_access_location_id,
)
from corehq.apps.locations.views import BaseLocationView, LocationsListView
from corehq.apps.reports.views import BaseProjectReportSectionView
from corehq.const import FILENAME_DATETIME_FORMAT
from corehq.util.files import safe_filename_header
from corehq.util.timezones.utils import get_timezone_for_user
from corehq.util.workbook_json.excel import WorkbookJSONError, get_workbook
from custom.icds.location_reassignment.const import (
    AWC_CODE,
    AWC_CODE_COLUMN,
    CASE_ID_COLUMN,
    CURRENT_SITE_CODE_COLUMN,
    HOUSEHOLD_ID_COLUMN,
    NEW_SITE_CODE_COLUMN,
    OPERATION_COLUMN,
    SHEETS_TO_IGNORE,
)
from custom.icds.location_reassignment.download import DownloadUsers
from custom.icds.location_reassignment.dumper import Dumper
from custom.icds.location_reassignment.forms import (
    LocationReassignmentRequestForm,
)
from custom.icds.location_reassignment.parser import (
    HouseholdReassignmentParser,
    OtherCasesReassignmentParser,
    Parser,
)
from custom.icds.location_reassignment.tasks import (
    email_household_details,
    email_other_cases_details,
    process_households_reassignment,
    process_location_reassignment,
    process_other_cases_reassignment,
)


@location_safe
@method_decorator([toggles.PERFORM_LOCATION_REASSIGNMENT.required_decorator()], name='dispatch')
class LocationReassignmentDownloadOnlyView(BaseProjectReportSectionView):
    section_name = ugettext_lazy("Download Location Reassignment Template")

    page_title = ugettext_lazy('Location Reassignment')
    urlname = 'location_reassignment_download_only'
    template_name = 'icds/location_reassignment.html'

    @property
    def page_context(self):
        context = super().page_context
        context.update({
            'bulk_upload': {
                "download_url": reverse('download_location_reassignment_template', args=[self.domain]),
                "adjective": _("locations"),
                "plural_noun": _("Location Reassignment Request file"),
            },
            'bulk_upload_form': None,
            "no_header": True,
        })
        return context


@method_decorator(require_can_edit_locations, name='dispatch')
class LocationReassignmentView(BaseLocationView):
    section_name = ugettext_lazy("Locations")

    page_title = ugettext_lazy('Location Reassignment')
    urlname = 'location_reassignment'
    template_name = 'icds/location_reassignment.html'

    def dispatch(self, *args, **kwargs):
        if not toggles.PERFORM_LOCATION_REASSIGNMENT.enabled(self.request.couch_user.username):
            raise Http404()
        return super().dispatch(*args, **kwargs)

    def section_url(self):
        return reverse(LocationsListView.urlname, args=[self.domain])

    @property
    def page_context(self):
        context = super().page_context
        context.update({
            'bulk_upload': {
                "download_url": reverse('download_location_reassignment_template', args=[self.domain]),
                "adjective": _("locations"),
                "plural_noun": _("Location Reassignment Request File"),
                "verb": _("Perform"),
                "help_link": "https://confluence.dimagi.com/display/ICDS/Location+Reassignment",
            },
        })
        context.update({
            'bulk_upload_form': get_bulk_upload_form(context, form_class=LocationReassignmentRequestForm),
            "no_header": True,
        })
        return context

    def post(self, request, *args, **kwargs):
        uploaded_file = request.FILES['bulk_upload_file']
        action_type = request.POST.get('action_type')
        workbook, errors = self._get_workbook(uploaded_file, action_type)
        if errors:
            [messages.error(request, error) for error in errors]
            return self.get(request, *args, **kwargs)
        parser = self._get_parser(action_type, workbook)
        errors = parser.parse()
        if errors:
            [messages.error(request, error) for error in errors]
        else:
            if action_type == LocationReassignmentRequestForm.EMAIL_HOUSEHOLDS:
                self._process_request_for_email_households(parser, request, uploaded_file.name)
            elif action_type == LocationReassignmentRequestForm.EMAIL_OTHER_CASES:
                self._process_request_for_email_other_cases(parser, request, uploaded_file.name)
            elif action_type == LocationReassignmentRequestForm.UPDATE:
                self._process_request_for_update(parser, request, uploaded_file.name)
            elif action_type == LocationReassignmentRequestForm.REASSIGN_HOUSEHOLDS:
                self._process_request_for_household_reassignment(parser, request, uploaded_file.name)
            elif action_type == LocationReassignmentRequestForm.REASSIGN_OTHER_CASES:
                self._process_request_for_other_cases_reassignment(parser, request, uploaded_file.name)
            else:
                return self._generate_summary_response(parser.valid_transitions, uploaded_file.name)
        return self.get(request, *args, **kwargs)

    def _get_parser(self, action_type, workbook):
        if action_type == LocationReassignmentRequestForm.REASSIGN_HOUSEHOLDS:
            return HouseholdReassignmentParser(self.domain, workbook)
        elif action_type == LocationReassignmentRequestForm.REASSIGN_OTHER_CASES:
            return OtherCasesReassignmentParser(self.domain, workbook)
        return Parser(self.domain, workbook)

    def _get_workbook(self, uploaded_file, action_type):
        try:
            workbook = get_workbook(uploaded_file)
        except WorkbookJSONError as e:
            return None, [str(e)]
        return workbook, self._validate_workbook(workbook, action_type)

    def _validate_workbook(self, workbook, action_type):
        """
        Ensure worksheets are present with titles as
        1. location type codes for request for operations related requests
        2. site codes of locations present in system for household reassignment
        Ensure mandatory headers
        :return list of errors
        """
        errors = []
        if not workbook.worksheets:
            errors.append(_("No worksheets in workbook"))
            return errors
        if action_type == LocationReassignmentRequestForm.REASSIGN_HOUSEHOLDS:
            mandatory_columns = {AWC_CODE_COLUMN, HOUSEHOLD_ID_COLUMN}
            location_site_codes = set([ws.title for ws in workbook.worksheets])
            site_codes_found = set(
                SQLLocation.objects.filter(domain=self.domain, site_code__in=location_site_codes)
                .values_list('site_code', flat=True))
            for worksheet in workbook.worksheets:
                errors.extend(self._validate_worksheet(worksheet, site_codes_found, mandatory_columns))
        elif action_type == LocationReassignmentRequestForm.REASSIGN_OTHER_CASES:
            mandatory_columns = {NEW_SITE_CODE_COLUMN, CASE_ID_COLUMN}
            location_site_codes = set([ws.title for ws in workbook.worksheets])
            site_codes_found = set(
                SQLLocation.objects.filter(domain=self.domain, site_code__in=location_site_codes)
                .values_list('site_code', flat=True))
            for worksheet in workbook.worksheets:
                errors.extend(self._validate_worksheet(worksheet, site_codes_found, mandatory_columns))
        else:
            mandatory_columns = {CURRENT_SITE_CODE_COLUMN, NEW_SITE_CODE_COLUMN, OPERATION_COLUMN}
            location_type_codes = [lt.code for lt in LocationType.objects.by_domain(self.domain)]
            for worksheet in workbook.worksheets:
                errors.extend(self._validate_worksheet(worksheet, location_type_codes, mandatory_columns))
        return errors

    @staticmethod
    def _validate_worksheet(worksheet, valid_titles, mandatory_columns):
        errors = []
        if worksheet.title in SHEETS_TO_IGNORE:
            return []
        if worksheet.title not in valid_titles:
            errors.append(_("Unexpected sheet {sheet_title}").format(sheet_title=worksheet.title))
            return errors

        columns = set(worksheet.headers)
        missing_columns = mandatory_columns - columns
        if missing_columns:
            errors.append(_("Missing columns {columns} for worksheet {sheet_title}").format(
                columns=", ".join(missing_columns), sheet_title=worksheet.title))
        return errors

    def _generate_summary_response(self, transitions, uploaded_filename):
        filename = uploaded_filename.split('.')[0] + " Summary"
        response_file = Dumper(self.domain).dump(transitions)
        response = HttpResponse(response_file, content_type="text/html; charset=utf-8")
        response['Content-Disposition'] = safe_filename_header(filename, 'xlsx')
        return response

    def _process_request_for_email_households(self, parser, request, uploaded_filename):
        awc_transitions = parser.valid_transitions_json(for_location_type=AWC_CODE).get(AWC_CODE)
        if awc_transitions:
            email_household_details.delay(self.domain, awc_transitions,
                                          uploaded_filename, request.user.email)
            messages.success(request, _(
                "Your request has been submitted. You will be updated via email."))
        else:
            messages.error(request, "No transitions found for %s" % AWC_CODE)

    def _process_request_for_email_other_cases(self, parser, request, uploaded_filename):
        all_transitions = []
        for location_type, transitions in parser.valid_transitions_json().items():
            all_transitions.extend(transitions)
        if all_transitions:
            email_other_cases_details.delay(self.domain, all_transitions,
                                            uploaded_filename, request.user.email)
            messages.success(request, _(
                "Your request has been submitted. You will be updated via email."))
        else:
            messages.error(request, "No transitions found")

    def _process_request_for_update(self, parser, request, uploaded_filename):
        process_location_reassignment.delay(
            self.domain, parser.valid_transitions_json(),
            uploaded_filename, request.user.email
        )
        messages.success(request, _(
            "Your request has been submitted. We will notify you via email once completed."))

    def _process_request_for_household_reassignment(self, parser, request, uploaded_filename):
        process_households_reassignment.delay(
            self.domain, parser.reassignments, uploaded_filename, request.user.email
        )
        messages.success(request, _(
            "Your request has been submitted. We will notify you via email once completed."))

    def _process_request_for_other_cases_reassignment(self, parser, request, uploaded_filename):
        process_other_cases_reassignment.delay(
            self.domain, parser.reassignments, uploaded_filename, request.user.email
        )
        messages.success(request, _(
            "Your request has been submitted. We will notify you via email once completed."))


@toggles.PERFORM_LOCATION_REASSIGNMENT.required_decorator()
@require_GET
@location_safe
def download_location_reassignment_template(request, domain):
    location_id = request.GET.get('location_id')

    if not location_id or not user_can_access_location_id(domain, request.couch_user, location_id):
        messages.error(request, _("Please select a location."))
        return HttpResponseRedirect(reverse(LocationReassignmentView.urlname, args=[domain]))

    location = SQLLocation.active_objects.get(location_id=location_id, domain=domain)
    response_file = DownloadUsers(location).dump()
    response = HttpResponse(response_file, content_type="text/html; charset=utf-8")
    timezone = get_timezone_for_user(request.couch_user, domain)
    creation_time = datetime.now(timezone).strftime(FILENAME_DATETIME_FORMAT)
    filename = f"[{domain}] {location.name} Location Reassignment Request Template {creation_time}"
    response['Content-Disposition'] = safe_filename_header(filename, 'xlsx')
    return response
