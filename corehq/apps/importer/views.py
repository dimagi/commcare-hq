import os.path
from django.http import HttpResponseRedirect
from casexml.apps.case.models import CommCareCase
from casexml.apps.phone.xml import get_case_xml
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.importer import base
from corehq.apps.importer.const import LookupErrors
import corehq.apps.importer.util as importer_util
from corehq.apps.importer.util import ExcelFile
from couchdbkit.exceptions import MultipleResultsFound, NoResultFound
from django.views.decorators.http import require_POST
from datetime import datetime, date
from xlrd import xldate_as_tuple
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import Permissions
from corehq.apps.app_manager.models import ApplicationBase
from soil.util import expose_download
from soil import DownloadBase

from casexml.apps.case.tests.util import CaseBlock
import uuid

from casexml.apps.case.xml import V2
from django.contrib import messages
from django.shortcuts import render
from django.utils.translation import ugettext as _

require_can_edit_data = require_permission(Permissions.edit_data)

EXCEL_SESSION_ID = "excel_id"
MAX_ALLOWED_ROWS = 500

def render_error(request, domain, message):
    """ Load error message and reload page for excel file load errors """
    messages.error(request, _(message))
    return HttpResponseRedirect(base.ImportCases.get_url(domain=domain))

@require_can_edit_data
def excel_config(request, domain):
    if request.method != 'POST':
        return HttpResponseRedirect(base.ImportCases.get_url(domain=domain))

    if not request.FILES:
        return render_error(request, domain, 'Please choose an Excel file to import.')

    named_columns = request.POST['named_columns'].lower()
    uses_headers = named_columns == 'yes'
    uploaded_file_handle = request.FILES['file']

    extension = os.path.splitext(uploaded_file_handle.name)[1][1:].strip().lower()

    # NOTE: We may not always be able to reference files from subsequent
    # views if your worker changes, so we have to store it elsewhere
    # using the soil framework.

    if extension not in ExcelFile.ALLOWED_EXTENSIONS:
        return render_error(request, domain,
                            'The Excel file you chose could not be processed. '
                            'Please check that it is saved as a Microsoft '
                            'Excel 97/2000 .xls file.')

    # stash content in the default storage for subsequent views
    file_ref = expose_download(uploaded_file_handle.read(), expiry=1*60*60)
    request.session[EXCEL_SESSION_ID] = file_ref.download_id
    spreadsheet = _get_spreadsheet(file_ref, uses_headers)

    if not spreadsheet:
        return _spreadsheet_expired(request, domain)

    columns = spreadsheet.get_header_columns()
    row_count = spreadsheet.get_num_rows()

    if row_count > MAX_ALLOWED_ROWS:
        return render_error(request, domain,
                            'Sorry, your spreadsheet is too big. Please reduce the '
                            'number of rows to less than %s and try again.' % MAX_ALLOWED_ROWS)
    if row_count == 0:
        return render_error(request, domain,
                            'Your spreadsheet is empty. '
                            'Please try again with a different spreadsheet.')

    case_types_from_apps = []
    # load types from all modules
    for row in ApplicationBase.view('app_manager/types_by_module',
                                 reduce=True,
                                 group=True,
                                 startkey=[domain],
                                 endkey=[domain,{}]).all():
        if not row['key'][1] in case_types_from_apps:
            case_types_from_apps.append(row['key'][1])

    case_types_from_cases = []
    # load types from all case records
    for row in CommCareCase.view('hqcase/types_by_domain',
                                 reduce=True,
                                 group=True,
                                 startkey=[domain],
                                 endkey=[domain,{}]).all():
        if not row['key'][1] in case_types_from_cases:
            case_types_from_cases.append(row['key'][1])

    # for this we just want cases that have data but aren't being used anymore
    case_types_from_cases = [case for case in case_types_from_cases
                             if case not in case_types_from_apps]

    case_types_from_cases = filter(lambda x: x not in case_types_from_apps, case_types_from_cases)

    if len(case_types_from_apps) == 0 or len(case_types_from_cases) == 0:
        return render_error(request, domain,
                            'No cases have been submitted to this domain. '
                            'You cannot update case details from an Excel '
                            'file until you have existing cases.')

    return render(request, "importer/excel_config.html", {
                                'named_columns': named_columns,
                                'columns': columns,
                                'case_types_from_cases': case_types_from_cases,
                                'case_types_from_apps': case_types_from_apps,
                                'domain': domain,
                                'report': {
                                    'name': 'Import: Configuration'
                                 },
                                'slug': base.ImportCases.slug})

@require_POST
@require_can_edit_data
def excel_fields(request, domain):
    named_columns = request.POST['named_columns'].lower()
    uses_headers = named_columns == 'yes'
    case_type = request.POST['case_type']
    search_column = request.POST['search_column']
    search_field = request.POST['search_field']
    create_new_cases = request.POST['create_new_cases']
    key_value_columns = request.POST['key_value_columns'].lower()
    key_column = ''
    value_column = ''

    download_ref = DownloadBase.get(request.session.get(EXCEL_SESSION_ID))

    spreadsheet = _get_spreadsheet(download_ref, uses_headers)
    if not spreadsheet:
        return _spreadsheet_expired(request, domain)

    columns = spreadsheet.get_header_columns()

    if key_value_columns == 'yes':
        key_column = request.POST['key_column']
        value_column = request.POST['value_column']

        excel_fields = []
        key_column_index = columns.index(key_column)

        # if key/value columns were specified, get all the unique keys listed
        if key_column_index:
            excel_fields = spreadsheet.get_unique_column_values(key_column_index)

        # concatenate unique key fields with the rest of the columns
        excel_fields = columns + excel_fields
        # remove key/value column names from list
        excel_fields.remove(key_column)
        if value_column in excel_fields:
            excel_fields.remove(value_column)
    else:
        excel_fields = columns

    case_fields = importer_util.get_case_properties(domain, case_type)

    # hide search column and matching case fields from the update list
    try:
        excel_fields.remove(search_column)
    except:
        pass

    try:
        case_fields.remove(search_field)
    except:
        pass

    return render(request, "importer/excel_fields.html", {
                                'named_columns': named_columns,
                                'case_type': case_type,
                                'search_column': search_column,
                                'search_field': search_field,
                                'create_new_cases': create_new_cases,
                                'key_column': key_column,
                                'value_column': value_column,
                                'columns': columns,
                                'excel_fields': excel_fields,
                                'excel_fields_range': range(len(excel_fields)),
                                'case_fields': case_fields,
                                'domain': domain,
                                'report': {
                                    'name': 'Import: Match columns to fields'
                                 },
                                'slug': base.ImportCases.slug})

@require_POST
@require_can_edit_data
def excel_commit(request, domain):
    named_columns = request.POST['named_columns'].lower()
    uses_headers = named_columns == 'yes'
    case_type = request.POST['case_type']
    search_field = request.POST['search_field']
    create_new_cases = True if request.POST['create_new_cases'].lower() == 'yes' else False

    download_ref = DownloadBase.get(request.session.get(EXCEL_SESSION_ID))
    spreadsheet = _get_spreadsheet(download_ref, uses_headers)
    if not spreadsheet:
        return _spreadsheet_expired(request, domain)

    if spreadsheet.has_errors:
        messages.error(request, _('The session containing the file you '
                                  'uploaded has expired - please upload '
                                  'a new one.'))
        return HttpResponseRedirect(base.ImportCases.get_url(domain=domain) + "?error=cache")

    columns = spreadsheet.get_header_columns()
    match_count = no_match_count = too_many_matches = 0
    cases = {}

    for i in range(spreadsheet.get_num_rows()):
        # skip first row if it is a header field
        if i == 0 and named_columns:
            continue

        row = spreadsheet.get_row(i)
        search_id = importer_util.parse_search_id(request, columns, row)
        case, error = importer_util.lookup_case(search_field, search_id, domain)

        if case:
            match_count += 1
        elif error == LookupErrors.NotFound:
            no_match_count += 1
            if not create_new_cases:
                continue
        elif error == LookupErrors.MultipleResults:
            too_many_matches += 1
            continue

        fields_to_update = importer_util.populate_updated_fields(request, columns, row)

        user = request.couch_user
        username = user.username
        user_id = user._id
        if not case:
            id = uuid.uuid4().hex
            owner_id = user_id

            caseblock = CaseBlock(
                create = True,
                case_id = id,
                version = V2,
                user_id = user_id,
                owner_id = owner_id,
                case_type = case_type,
                external_id = search_id if search_field == 'external_id' else '',
                update = fields_to_update
            )
            importer_util.submit_case_block(caseblock, domain, username, user_id)
        elif case and case.type == case_type:
            caseblock = CaseBlock(
                create = False,
                case_id = case._id,
                version = V2,
                update = fields_to_update
            )
            importer_util.submit_case_block(caseblock, domain, username, user_id)

    # unset filename session var
    try:
        del request.session[EXCEL_SESSION_ID]
    except KeyError:
        pass

    return render(request, "importer/excel_commit.html", {
                                'match_count': match_count,
                                'no_match_count': no_match_count,
                                'too_many_matches': too_many_matches,
                                'domain': domain,
                                'report': {
                                    'name': 'Import: Completed'
                                 },
                                'slug': base.ImportCases.slug})

def _spreadsheet_expired(req, domain):
    messages.error(req, _('Sorry, your session has expired. Please start over and try again.'))
    return HttpResponseRedirect(base.ImportCases.get_url(domain))

def _get_spreadsheet(download_ref, column_headers=True):
    if not download_ref:
        return None
    return ExcelFile(download_ref.get_filename(), column_headers)
