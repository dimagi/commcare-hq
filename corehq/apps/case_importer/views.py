from __future__ import absolute_import
import os.path
from django.http import HttpResponseRedirect
from django.utils.datastructures import MultiValueDictKeyError
from corehq.apps.app_manager.dbaccessors import get_case_types_from_apps
from corehq.apps.case_importer import base
from corehq.apps.case_importer import util as importer_util
from corehq.apps.case_importer.exceptions import ImporterError
from django.views.decorators.http import require_POST
from corehq.apps.case_importer.suggested_fields import get_suggested_case_fields
from corehq.apps.case_importer.tracking.case_upload_tracker import CaseUpload

from corehq.apps.case_importer.util import get_importer_error_message
from corehq.apps.reports.analytics.esaccessors import get_case_types_for_domain_es
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import Permissions

from django.contrib import messages
from django.shortcuts import render
from django.utils.translation import ugettext as _

require_can_edit_data = require_permission(Permissions.edit_data)

EXCEL_SESSION_ID = "excel_id"


def render_error(request, domain, message):
    """ Load error message and reload page for excel file load errors """
    messages.error(request, _(message))
    return HttpResponseRedirect(base.ImportCases.get_url(domain=domain))


@require_can_edit_data
def excel_config(request, domain):
    """
    Step one of three.

    This is the initial post when the user uploads the excel file

    """
    if request.method != 'POST':
        return HttpResponseRedirect(base.ImportCases.get_url(domain=domain))

    if not request.FILES:
        return render_error(request, domain, 'Please choose an Excel file to import.')

    uploaded_file_handle = request.FILES['file']

    extension = os.path.splitext(uploaded_file_handle.name)[1][1:].strip().lower()

    # NOTE: We may not always be able to reference files from subsequent
    # views if your worker changes, so we have to store it elsewhere
    # using the soil framework.

    if extension not in importer_util.ALLOWED_EXTENSIONS:
        return render_error(request, domain,
                            'The file you chose could not be processed. '
                            'Please check that it is saved as a Microsoft '
                            'Excel file.')

    # stash content in the default storage for subsequent views
    case_upload = CaseUpload.create(uploaded_file_handle,
                                    filename=uploaded_file_handle.name)

    request.session[EXCEL_SESSION_ID] = case_upload.upload_id
    try:
        case_upload.check_file()
    except ImporterError as e:
        return render_error(request, domain, get_importer_error_message(e))

    with case_upload.get_spreadsheet() as spreadsheet:
        columns = spreadsheet.get_header_columns()
        row_count = spreadsheet.max_row

    if row_count == 0:
        return render_error(request, domain,
                            'Your spreadsheet is empty. '
                            'Please try again with a different spreadsheet.')

    case_types_from_apps = get_case_types_from_apps(domain)
    unrecognized_case_types = [t for t in get_case_types_for_domain_es(domain)
                               if t not in case_types_from_apps]

    if len(case_types_from_apps) == 0 and len(unrecognized_case_types) == 0:
        return render_error(
            request,
            domain,
            'No cases have been submitted to this domain and there are no '
            'applications yet. You cannot import case details from an Excel '
            'file until you have existing cases or applications.'
        )

    return render(
        request,
        "case_importer/excel_config.html", {
            'columns': columns,
            'unrecognized_case_types': unrecognized_case_types,
            'case_types_from_apps': case_types_from_apps,
            'domain': domain,
            'report': {
                'name': 'Import: Configuration'
            },
            'slug': base.ImportCases.slug
        }
    )


@require_POST
@require_can_edit_data
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
        Which column of the excel file we are using to specify either
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
        messages.error(request, _('It looks like you may have accessed this page from a stale page. '
                                  'Please start over.'))
        return _spreadsheet_expired(request, domain)

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

    return render(
        request,
        "case_importer/excel_fields.html", {
            'case_type': case_type,
            'search_column': search_column,
            'search_field': search_field,
            'create_new_cases': create_new_cases,
            'columns': columns,
            'excel_fields': excel_fields,
            'case_field_specs': case_field_specs,
            'domain': domain,
            'report': {
                'name': 'Import: Match columns to fields'
            },
            'slug': base.ImportCases.slug
        }
    )


@require_POST
@require_can_edit_data
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


def _spreadsheet_expired(req, domain):
    messages.error(req, _('Sorry, your session has expired. Please start over and try again.'))
    return HttpResponseRedirect(base.ImportCases.get_url(domain))
