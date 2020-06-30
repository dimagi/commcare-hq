import os.path

from django.contrib import messages
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.utils.datastructures import MultiValueDictKeyError
from django.utils.html import format_html
from django.utils.translation import ugettext as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from corehq.apps.hqwebapp.decorators import waf_allow
from dimagi.utils.web import json_response

from corehq.apps.app_manager.dbaccessors import get_case_types_from_apps
from corehq.apps.app_manager.helpers.validators import validate_property
from corehq.apps.case_importer import base
from corehq.apps.case_importer import util as importer_util
from corehq.apps.case_importer.base import location_safe_case_imports_enabled
from corehq.apps.case_importer.const import MAX_CASE_IMPORTER_COLUMNS
from corehq.apps.case_importer.exceptions import ImporterError, ImporterRawError
from corehq.apps.case_importer.suggested_fields import (
    get_suggested_case_fields,
)
from corehq.apps.case_importer.tracking.case_upload_tracker import CaseUpload
from corehq.apps.case_importer.util import get_importer_error_message
from corehq.apps.domain.decorators import api_auth
from corehq.apps.locations.permissions import conditionally_location_safe
from corehq.apps.reports.analytics.esaccessors import (
    get_case_types_for_domain_es,
)
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import Permissions
from corehq.util.view_utils import absolute_reverse
from corehq.util.workbook_reading import valid_extensions, SpreadsheetFileExtError

require_can_edit_data = require_permission(Permissions.edit_data)

EXCEL_SESSION_ID = "excel_id"


def render_error(request, domain, message):
    """ Load error message and reload page for Excel file load errors """
    messages.error(request, _(message))
    return HttpResponseRedirect(base.ImportCases.get_url(domain=domain))


def validate_column_names(column_names, invalid_column_names):
    for column_name in column_names:
        try:
            validate_property(column_name, allow_parents=False)
        except ValueError:
            invalid_column_names.add(column_name)


# Cobble together the context needed to render breadcrumbs that class-based views get from BasePageView
# For use by function-based views that extend hqwebapp/base_section.html
def _case_importer_breadcrumb_context(page_name, domain):
    return {
        'current_page': {
            'title': page_name,
            'page_name': page_name,
            'parents': [base.ImportCases.current_page_context(domain=domain)]
        },
        'section': base.ImportCases.section_context(),
    }


@waf_allow('XSS_BODY')
@require_can_edit_data
@conditionally_location_safe(location_safe_case_imports_enabled)
def excel_config(request, domain):
    """
    Step one of three.

    This is the initial post when the user uploads the Excel file

    """
    if request.method != 'POST':
        return HttpResponseRedirect(base.ImportCases.get_url(domain=domain))

    if not request.FILES:
        return render_error(request, domain, 'Please choose an Excel file to import.')

    uploaded_file_handle = request.FILES['file']
    try:
        case_upload, context = _process_file_and_get_upload(uploaded_file_handle, request, domain)
    except ImporterError as e:
        return render_error(request, domain, get_importer_error_message(e))
    except SpreadsheetFileExtError:
        return render_error(request, domain, _("Please upload file with extension .xls or .xlsx"))

    context.update(_case_importer_breadcrumb_context(_('Case Options'), domain))
    return render(request, "case_importer/excel_config.html", context)


def _process_file_and_get_upload(uploaded_file_handle, request, domain):
    extension = os.path.splitext(uploaded_file_handle.name)[1][1:].strip().lower()

    # NOTE: We may not always be able to reference files from subsequent
    # views if your worker changes, so we have to store it elsewhere
    # using the soil framework.

    if extension not in valid_extensions:
        raise SpreadsheetFileExtError(
            'The file you chose could not be processed. '
            'Please check that it is saved as a Microsoft '
            'Excel file.'
        )

    # stash content in the default storage for subsequent views
    case_upload = CaseUpload.create(uploaded_file_handle,
                                    filename=uploaded_file_handle.name,
                                    domain=domain)

    request.session[EXCEL_SESSION_ID] = case_upload.upload_id

    case_upload.check_file()
    invalid_column_names = set()
    with case_upload.get_spreadsheet() as spreadsheet:
        columns = spreadsheet.get_header_columns()
        validate_column_names(columns, invalid_column_names)
        row_count = spreadsheet.max_row

    if invalid_column_names:
        error_message = format_html(
            _("Column names must be <a target='_blank' href='https://www.w3schools.com/xml/xml_elements.asp'>"
              "valid XML elements</a> and cannot start with a number or contain spaces or most special characters."
              " Please update the following: {}.").format(
                ', '.join(invalid_column_names)))
        raise ImporterRawError(error_message)

    if row_count == 0:
        raise ImporterError('Your spreadsheet is empty. Please try again with a different spreadsheet.')

    if len(columns) > MAX_CASE_IMPORTER_COLUMNS:
        raise ImporterError(
            'Your spreadsheet has too many columns. '
            'A maximum of %(max_columns)s is supported.'
            % {'max_columns': MAX_CASE_IMPORTER_COLUMNS})

    case_types_from_apps = sorted(get_case_types_from_apps(domain))
    unrecognized_case_types = sorted([t for t in get_case_types_for_domain_es(domain)
                                      if t not in case_types_from_apps])

    if len(case_types_from_apps) == 0 and len(unrecognized_case_types) == 0:
        raise ImporterError(
            'No cases have been submitted to this domain and there are no '
            'applications yet. You cannot import case details from an Excel '
            'file until you have existing cases or applications.')

    context = {
        'columns': columns,
        'unrecognized_case_types': unrecognized_case_types,
        'case_types_from_apps': case_types_from_apps,
        'domain': domain,
        'slug': base.ImportCases.slug,
    }
    return case_upload, context


@require_POST
@require_can_edit_data
@conditionally_location_safe(location_safe_case_imports_enabled)
def excel_fields(request, domain):
    """
    Step two of three.

    Important values that are grabbed from the POST or defined by
    the user on this page:

    case_type:
        The type of case we are matching to. When creating new cases,
        this is the type they will be created as. When updating
        existing cases, this is the type that we will search for.
        If the wrong case type is used when looking up existing cases,
        we will not update them.

    create_new_cases:
        A boolean that controls whether or not the user wanted
        to create new cases for any case that doesn't have a matching
        case id in the upload.

    search_column:
        Which column of the Excel file we are using to specify either
        case ids or external ids. This is, strangely, required. If
        creating new cases only you would expect these to be blank with
        the create_new_cases flag set.

    search_field:
        Either case id or external id, determines which type of
        identification we are using to match to cases.

    """
    case_type = request.POST['case_type']
    try:
        search_column = request.POST['search_column']
    except MultiValueDictKeyError:
        # this is only true if your configuration is messed up in an irreparable way
        messages.error(request, _('The Excel file you are trying to import does not have any headers.'))
        return HttpResponseRedirect(base.ImportCases.get_url(domain))

    search_field = request.POST['search_field']
    create_new_cases = request.POST.get('create_new_cases') == 'on'

    case_upload = CaseUpload.get(request.session.get(EXCEL_SESSION_ID))

    try:
        case_upload.check_file()
    except ImporterError as e:
        return render_error(request, domain, get_importer_error_message(e))

    with case_upload.get_spreadsheet() as spreadsheet:
        columns = spreadsheet.get_header_columns()
        excel_fields = columns

    # hide search column and matching case fields from the update list
    if search_column in excel_fields:
        excel_fields.remove(search_column)

    field_specs = get_suggested_case_fields(
        domain, case_type, exclude=[search_field])

    case_field_specs = [field_spec.to_json() for field_spec in field_specs]

    context = {
        'case_type': case_type,
        'search_column': search_column,
        'search_field': search_field,
        'create_new_cases': create_new_cases,
        'columns': columns,
        'excel_fields': excel_fields,
        'case_field_specs': case_field_specs,
        'domain': domain,
    }
    context.update(_case_importer_breadcrumb_context(_('Match Excel Columns to Case Properties'), domain))
    return render(request, "case_importer/excel_fields.html", context)


@require_POST
@require_can_edit_data
@conditionally_location_safe(location_safe_case_imports_enabled)
def excel_commit(request, domain):
    """
    Step three of three.

    This page is submitted with the list of column to
    case property mappings for this upload.

    The config variable is an ImporterConfig object that
    has everything gathered from previous steps, with the
    addition of all the field data. See that class for
    more information.
    """
    config = importer_util.ImporterConfig.from_request(request)

    excel_id = request.session.get(EXCEL_SESSION_ID)

    case_upload = CaseUpload.get(excel_id)
    try:
        case_upload.check_file()
    except ImporterError as e:
        return render_error(request, domain, get_importer_error_message(e))

    case_upload.trigger_upload(domain, config)

    request.session.pop(EXCEL_SESSION_ID, None)

    return HttpResponseRedirect(base.ImportCases.get_url(domain))


@waf_allow('XSS_BODY')
@csrf_exempt
@require_POST
@api_auth
@require_can_edit_data
def bulk_case_upload_api(request, domain, **kwargs):
    try:
        response = _bulk_case_upload_api(request, domain)
        return response
    except ImporterError as e:
        error = get_importer_error_message(e)
    except SpreadsheetFileExtError:
        error = "Please upload file with one of the following extensions: {}".format(
            ', '.join(valid_extensions)
        )
    return json_response({'code': 500, 'message': _(error)}, status_code=500)


def _bulk_case_upload_api(request, domain):
    try:
        upload_file = request.FILES["file"]
        case_type = request.POST["case_type"]
        if not upload_file or not case_type:
            raise Exception
    except Exception:
        raise ImporterError("Invalid POST request. "
        "Both 'file' and 'case_type' are required")

    search_field = request.POST.get('search_field', 'case_id')
    create_new_cases = request.POST.get('create_new_cases') == 'on'

    if search_field == 'case_id':
        default_search_column = 'case_id'
    elif search_field == 'external_id':
        default_search_column = 'external_id'
    else:
        raise ImporterError("Illegal value for search_field: %s" % search_field)

    search_column = request.POST.get('search_column', default_search_column)
    name_column = request.POST.get('name_column', 'name')

    upload_comment = request.POST.get('comment')

    case_upload, context = _process_file_and_get_upload(upload_file, request, domain)

    case_upload.check_file()

    with case_upload.get_spreadsheet() as spreadsheet:
        columns = spreadsheet.get_header_columns()
        excel_fields = columns

    # hide search column and matching case fields from the update list
    if search_column in excel_fields:
        excel_fields.remove(search_column)

    custom_fields = []
    case_fields = []

    #Create the field arrays for the importer in the same format
    #as the "Step 2" Web UI from the manual process
    for f in excel_fields:
        if f == name_column:
            custom_fields.append("")
            case_fields.append("name")
        else:
            custom_fields.append(f)
            case_fields.append("")

    config = importer_util.ImporterConfig(
            couch_user_id=request.couch_user._id,
            excel_fields=excel_fields,
            case_fields=case_fields,
            custom_fields=custom_fields,
            search_column=search_column,
            case_type=case_type,
            search_field=search_field,
            create_new_cases=create_new_cases)

    case_upload.trigger_upload(domain, config, comment=upload_comment)

    upload_id = case_upload.upload_id
    status_url = absolute_reverse('case_importer_upload_status', args=(domain, upload_id))

    return json_response({"code": 200, "message": "success", "status_url": status_url})
