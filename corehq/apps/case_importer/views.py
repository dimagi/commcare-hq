import os.path

from django.contrib import messages
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.utils.datastructures import MultiValueDictKeyError
from django.utils.html import format_html
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from dimagi.utils.logging import notify_error
from dimagi.utils.web import json_response

from corehq.apps.app_manager.dbaccessors import get_case_types_from_apps
from corehq.apps.app_manager.helpers.validators import validate_property
from corehq.apps.case_importer import base
from corehq.apps.case_importer import util as importer_util
from corehq.apps.case_importer.base import location_safe_case_imports_enabled
from corehq.apps.case_importer.const import (
    ALL_CASE_TYPE_IMPORT,
    MAX_CASE_IMPORTER_COLUMNS,
)
from corehq.apps.case_importer.exceptions import (
    CustomImporterError,
    ImporterError,
    ImporterFileNotFound,
    ImporterRawError,
)
from corehq.apps.case_importer.extension_points import (
    custom_case_upload_file_operations,
)
from corehq.apps.case_importer.suggested_fields import (
    get_suggested_case_fields,
)
from corehq.apps.case_importer.tracking.case_upload_tracker import CaseUpload
from corehq.apps.case_importer.util import (
    RESERVED_FIELDS,
    get_importer_error_message,
)
from corehq.apps.data_dictionary.util import (
    get_data_dict_case_types,
    get_data_dict_deprecated_case_types,
)
from corehq.apps.domain.decorators import api_auth
from corehq.apps.hqwebapp.decorators import waf_allow
from corehq.apps.locations.permissions import conditionally_location_safe
from corehq.apps.reports.analytics.esaccessors import (
    get_case_types_for_domain_es,
)
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import HqPermissions
from corehq.toggles import DOMAIN_PERMISSIONS_MIRROR
from corehq.util.view_utils import absolute_reverse
from corehq.util.workbook_reading import (
    SpreadsheetFileExtError,
    SpreadsheetFileInvalidError,
    open_any_workbook,
    valid_extensions,
)

require_can_edit_data = require_permission(HqPermissions.edit_data)

EXCEL_SESSION_ID = "excel_id"


def render_error(request, domain, message):
    """ Load error message and reload page for Excel file load errors """
    messages.error(request, _(message))
    return HttpResponseRedirect(base.ImportCases.get_url(domain=domain))


def validate_column_names(column_names, invalid_column_names):
    for column_name in column_names:
        try:
            validate_property(column_name, allow_parents=False)
        except (ValueError, TypeError):
            invalid_column_names.add(str(column_name))


# Cobble together the context needed to render breadcrumbs that class-based views get from BasePageView
# For use by function-based views that extend hqwebapp/bootstrap3/base_section.html
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
        case_upload, context = _process_file_and_get_upload(
            uploaded_file_handle, request, domain, max_columns=MAX_CASE_IMPORTER_COLUMNS
        )
    except ImporterFileNotFound as e:
        notify_error(f"Import file not found after initial upload: {str(e)}")
        return render_error(request, domain, get_importer_error_message(e))
    except ImporterError as e:
        return render_error(request, domain, get_importer_error_message(e))
    except SpreadsheetFileExtError:
        return render_error(request, domain, _("Please upload file with extension .xls or .xlsx"))

    context.update(_case_importer_breadcrumb_context(_('Case Options'), domain))
    return render(request, "case_importer/excel_config.html", context)


def _get_workbook_sheet_names(case_upload):
    with open_any_workbook(case_upload.get_tempfile()) as workbook:
        return [worksheet.title for worksheet in workbook.worksheets]


def _process_spreadsheet_columns(spreadsheet, max_columns=None):
    invalid_column_names = set()
    columns = spreadsheet.get_header_columns()
    validate_column_names(columns, invalid_column_names)
    row_count = spreadsheet.max_row

    if invalid_column_names:
        error_message = format_html(_(
            'Column names correspond to <a target="_blank" href="https://confl'
            'uence.dimagi.com/display/commcarepublic/Case+Configuration">case '
            'property names</a>. They must start with a letter, and can only '
            'contain letters, numbers and underscores. Please update the '
            'following: {}.').format(', '.join(invalid_column_names)))
        raise ImporterRawError(error_message)

    if row_count == 0:
        raise ImporterError(_('Your spreadsheet is empty. Please try again with a different spreadsheet.'))

    if max_columns is not None and len(columns) > max_columns:
        raise ImporterError(_(
            'Your spreadsheet has too many columns. '
            'A maximum of %(max_columns)s is supported.'
        ) % {'max_columns': MAX_CASE_IMPORTER_COLUMNS})

    return columns


def _process_bulk_sheets(case_upload, worksheet_titles):
    for index in range(len(worksheet_titles)):
        with case_upload.get_spreadsheet(index) as spreadsheet:
            _process_spreadsheet_columns(spreadsheet, MAX_CASE_IMPORTER_COLUMNS)

    # Set columns to only be caseid, as this is the only option a user should have when
    # doing a bulk case import.
    return ['caseid']


def _process_single_sheet(case_upload):
    with case_upload.get_spreadsheet() as spreadsheet:
        return _process_spreadsheet_columns(spreadsheet, MAX_CASE_IMPORTER_COLUMNS)


def _is_bulk_import(domain, case_types_from_apps, unrecognized_case_types, worksheet_titles):
    '''
    It is a bulk import if every sheet name is a case type in the project space.
    This does introduce the limitation that new cases for new case types cannot be bulk imported
    unless they are first added to an application or the Data Dictionary.
    '''
    data_dict_case_types = get_data_dict_case_types(domain)
    all_case_types = set(case_types_from_apps + unrecognized_case_types) | data_dict_case_types
    is_bulk_import = len(set(worksheet_titles) - all_case_types) == 0
    return is_bulk_import


def _process_file_and_get_upload(uploaded_file_handle, request, domain, max_columns=None):
    extension = os.path.splitext(uploaded_file_handle.name)[1][1:].strip().lower()

    # NOTE: We may not always be able to reference files from subsequent
    # views if your worker changes, so we have to store it elsewhere
    # using the soil framework.

    if extension not in valid_extensions:
        raise SpreadsheetFileExtError(_(
            'The file you chose could not be processed. '
            'Please check that it is saved as a Microsoft '
            'Excel file.'
        ))

    # stash content in the default storage for subsequent views
    case_upload = CaseUpload.create(uploaded_file_handle,
                                    filename=uploaded_file_handle.name,
                                    domain=domain)

    request.session[EXCEL_SESSION_ID] = case_upload.upload_id

    case_upload.check_file()

    worksheet_titles = _get_workbook_sheet_names(case_upload)
    case_types_from_apps = sorted(get_case_types_from_apps(domain))
    unrecognized_case_types = sorted([t for t in get_case_types_for_domain_es(domain)
                                      if t not in case_types_from_apps])

    if len(case_types_from_apps) == 0 and len(unrecognized_case_types) == 0:
        raise ImporterError(_(
            'Your project does not use cases yet. To import cases from Excel, '
            'you must first create an application with a case list.'
        ))

    is_bulk_import = _is_bulk_import(domain, case_types_from_apps, unrecognized_case_types, worksheet_titles)
    columns = []
    try:
        if is_bulk_import:
            columns = _process_bulk_sheets(case_upload, worksheet_titles)
        else:
            columns = _process_single_sheet(case_upload)
    except ImporterRawError as e:
        raise ImporterRawError(e) from e
    except ImporterError as e:
        raise ImporterError(e) from e

    data_dict_deprecated_case_types = get_data_dict_deprecated_case_types(domain)
    deprecated_case_types_used = []
    if is_bulk_import:
        deprecated_case_types_used = set(worksheet_titles).intersection(data_dict_deprecated_case_types)
    else:
        # Remove deprecated case types as options. We only do that here as we don't want to remove
        # deprecated case types when determing if the import is a bulk case import
        case_types_from_apps = set(case_types_from_apps) - data_dict_deprecated_case_types
        unrecognized_case_types = set(unrecognized_case_types) - data_dict_deprecated_case_types

    error_messages = custom_case_upload_file_operations(domain=domain, case_upload=case_upload)
    if error_messages:
        raise CustomImporterError("; ".join(error_messages))

    context = {
        'columns': columns,
        'unrecognized_case_types': [] if is_bulk_import else unrecognized_case_types,
        'case_types_from_apps': [ALL_CASE_TYPE_IMPORT] if is_bulk_import else case_types_from_apps,
        'domain': domain,
        'slug': base.ImportCases.slug,
        'is_bulk_import': is_bulk_import,
        'deprecated_case_types_used': deprecated_case_types_used,
    }
    return case_upload, context


def _process_excel_mapping(domain, spreadsheet, search_column):
    columns = spreadsheet.get_header_columns()
    excel_fields = columns

    # hide search column and matching case fields from the update list
    if search_column in excel_fields:
        excel_fields.remove(search_column)

    # 'domain' case property cannot be created if domain mirror flag is enabled,
    # as this enables a multi-domain case import.
    # see: https://dimagi-dev.atlassian.net/browse/USH-81
    mirroring_enabled = False
    if 'domain' in excel_fields and DOMAIN_PERMISSIONS_MIRROR.enabled(domain):
        excel_fields.remove('domain')
        mirroring_enabled = True

    return columns, excel_fields, mirroring_enabled


def _create_bulk_configs(domain, request, case_upload):
    all_configs = []
    worksheet_titles = _get_workbook_sheet_names(case_upload)
    for index, title in enumerate(worksheet_titles):
        with case_upload.get_spreadsheet(index) as spreadsheet:
            _, excel_fields, _ = _process_excel_mapping(
                domain,
                spreadsheet,
                request.POST['search_field']
            )
            excel_fields = list(set(excel_fields) - set(RESERVED_FIELDS))
            config = importer_util.ImporterConfig.from_dict({
                'couch_user_id': request.couch_user._id,
                'excel_fields': excel_fields,
                'case_fields': excel_fields,
                'custom_fields': [''] * len(excel_fields),
                'search_column': request.POST['search_column'],
                'case_type': title,
                'search_field': request.POST['search_field'],
                'create_new_cases': request.POST['create_new_cases'] == 'True',
            })
            all_configs.append(config)
    return all_configs


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
        we will not update them. For a bulk import, this will be displayed
        as the special value for bulk case import/export, and the fetching of
        the case types will be handled in the next step.

    create_new_cases:
        A boolean that controls whether or not the user wanted
        to create new cases for any case that doesn't have a matching
        case id in the upload.

    search_column:
        Which column of the Excel file we are using to specify either
        case ids or external ids. This is, strangely, required. If
        creating new cases only you would expect these to be blank with
        the create_new_cases flag set. This will default to case ids only
        when doing a bulk import.

    search_field:
        Either case id or external id, determines which type of
        identification we are using to match to cases. If doing a bulk import,
        we will default to using case id only.

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
        columns, excel_fields, mirroring_enabled = _process_excel_mapping(domain, spreadsheet, search_column)

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
        'mirroring_enabled': mirroring_enabled,
        'is_bulk_import': request.POST.get('is_bulk_import', 'False') == 'True',
    }
    context.update(_case_importer_breadcrumb_context(_('Match Excel Columns to Case Properties'), domain))
    return render(request, "case_importer/bootstrap3/excel_fields.html", context)


@require_POST
@require_can_edit_data
@conditionally_location_safe(location_safe_case_imports_enabled)
def excel_commit(request, domain):
    """
    Step three of three.

    This page is submitted with the list of column to
    case property mappings for this upload. If it is a bulk case import however,
    this is where we will generate the configs for each case type in the import file.

    The config variable is an ImporterConfig object that
    has everything gathered from previous steps, with the
    addition of all the field data. See that class for
    more information.
    """
    excel_id = request.session.get(EXCEL_SESSION_ID)

    case_upload = CaseUpload.get(excel_id)
    try:
        case_upload.check_file()
    except ImporterError as e:
        return render_error(request, domain, get_importer_error_message(e))

    case_type = request.POST['case_type']
    all_configs = []
    if case_type == ALL_CASE_TYPE_IMPORT:
        all_configs = _create_bulk_configs(domain, request, case_upload)
    else:
        config = importer_util.ImporterConfig.from_request(request)
        all_configs = [config]

    case_upload.trigger_upload(domain, all_configs, is_bulk=(case_type == ALL_CASE_TYPE_IMPORT))
    request.session.pop(EXCEL_SESSION_ID, None)

    return HttpResponseRedirect(base.ImportCases.get_url(domain))


@waf_allow('XSS_BODY')
@csrf_exempt
@require_POST
@api_auth()
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
    except SpreadsheetFileInvalidError as e:
        error = str(e)
    return json_response({'code': 500, 'message': error}, status_code=500)


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

    all_configs = []
    if context['is_bulk_import']:
        all_configs = _create_bulk_configs(domain, request, case_upload)
    else:
        with case_upload.get_spreadsheet() as spreadsheet:
            _, excel_fields, _ = _process_excel_mapping(domain, spreadsheet, search_column)

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

        all_configs = [importer_util.ImporterConfig(
            couch_user_id=request.couch_user._id,
            excel_fields=excel_fields,
            case_fields=case_fields,
            custom_fields=custom_fields,
            search_column=search_column,
            case_type=case_type,
            search_field=search_field,
            create_new_cases=create_new_cases)]

    case_upload.trigger_upload(domain, all_configs, comment=upload_comment, is_bulk=context['is_bulk_import'])

    upload_id = case_upload.upload_id
    status_url = absolute_reverse('case_importer_upload_status', args=(domain, upload_id))

    return json_response({"code": 200, "message": "success", "status_url": status_url})
