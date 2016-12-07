import os.path
from django.http import HttpResponseRedirect
from django.utils.datastructures import MultiValueDictKeyError
from corehq.apps.app_manager.dbaccessors import get_case_types_from_apps
from corehq.apps.case_importer import base
from corehq.apps.case_importer import util as importer_util
from corehq.apps.case_importer.exceptions import ImporterError
from corehq.apps.case_importer.tasks import bulk_import_async
from django.views.decorators.http import require_POST

from corehq.apps.case_importer.util import get_case_properties_for_case_type, get_importer_error_message
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import Permissions
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.util.files import file_extention_from_filename
from soil.exceptions import TaskFailedError
from soil.util import expose_cached_download, get_download_context
from soil import DownloadBase
from django.template.context import RequestContext

from django.contrib import messages
from django.shortcuts import render, render_to_response
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

    named_columns:
        Whether or not the first row of the excel sheet contains
        header strings for the columns. This defaults to True and
        should potentially not be an option as it is always used
        due to how important it is to see column headers
        in the rest of the importer.
    """
    if request.method != 'POST':
        return HttpResponseRedirect(base.ImportCases.get_url(domain=domain))

    if not request.FILES:
        return render_error(request, domain, 'Please choose an Excel file to import.')

    named_columns = request.POST.get('named_columns') == "on"
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
    file_ref = expose_cached_download(
        uploaded_file_handle.read(),
        expiry=1*60*60,
        file_extension=file_extention_from_filename(uploaded_file_handle.name),
    )
    request.session[EXCEL_SESSION_ID] = file_ref.download_id
    try:
        importer_util.open_spreadsheet_download_ref(file_ref, named_columns)
    except ImporterError as e:
        return render_error(request, domain, get_importer_error_message(e))

    with importer_util.get_spreadsheet(file_ref.get_filename(), named_columns) as spreadsheet:
        columns = spreadsheet.get_header_columns()
        row_count = spreadsheet.max_row

    if row_count == 0:
        return render_error(request, domain,
                            'Your spreadsheet is empty. '
                            'Please try again with a different spreadsheet.')

    case_types_from_apps = get_case_types_from_apps(domain)
    unrecognized_case_types = [t for t in CaseAccessors(domain).get_case_types()
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
            'named_columns': named_columns,
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

    named_columns:
        Passed through from last step, see that for documentation

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

    key_column/value_column:
        These correspond to an advanced feature allowing a user
        to modify a single case with multiple rows.
    """
    named_columns = request.POST['named_columns']
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
    key_value_columns = request.POST.get('key_value_columns') == 'on'
    key_column = ''
    value_column = ''

    download_ref = DownloadBase.get(request.session.get(EXCEL_SESSION_ID))

    try:
        importer_util.open_spreadsheet_download_ref(download_ref, named_columns)
    except ImporterError as e:
        return render_error(request, domain, get_importer_error_message(e))

    with importer_util.get_spreadsheet(download_ref.get_filename(), named_columns) as spreadsheet:
        columns = spreadsheet.get_header_columns()

        if key_value_columns:
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

    case_fields = get_case_properties_for_case_type(domain, case_type)

    # hide search column and matching case fields from the update list
    try:
        excel_fields.remove(search_column)
    except:
        pass

    try:
        case_fields.remove(search_field)
    except:
        pass

    # we can't actually update this so don't show it
    try:
        case_fields.remove('type')
    except:
        pass

    return render(
        request,
        "case_importer/excel_fields.html", {
            'named_columns': named_columns,
            'case_type': case_type,
            'search_column': search_column,
            'search_field': search_field,
            'create_new_cases': create_new_cases,
            'key_column': key_column,
            'value_column': value_column,
            'columns': columns,
            'excel_fields': excel_fields,
            'case_fields': case_fields,
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

    excel_ref = DownloadBase.get(excel_id)
    try:
        importer_util.open_spreadsheet_download_ref(excel_ref, config.named_columns)
    except ImporterError as e:
        return render_error(request, domain, get_importer_error_message(e))

    download = DownloadBase()
    download.set_task(bulk_import_async.delay(
        config,
        domain,
        excel_id,
    ))

    try:
        del request.session[EXCEL_SESSION_ID]
    except KeyError:
        pass

    return render(
        request,
        "case_importer/excel_commit.html", {
            'download_id': download.download_id,
            'template': 'case_importer/partials/import_status.html',
            'domain': domain,
            'report': {
                'name': 'Import: Completed'
            },
            'slug': base.ImportCases.slug
        }
    )


@require_can_edit_data
def importer_job_poll(request, domain, download_id, template="case_importer/partials/import_status.html"):
    try:
        download_context = get_download_context(download_id, check_state=True)
    except TaskFailedError as e:
        context = RequestContext(request)
        context.update({'error': e.errors, 'url': base.ImportCases.get_url(domain=domain)})
        return render_to_response('case_importer/partials/import_error.html', context_instance=context)
    else:
        context = RequestContext(request)
        context.update(download_context)
        context['url'] = base.ImportCases.get_url(domain=domain)
        return render_to_response(template, context_instance=context)


def _spreadsheet_expired(req, domain):
    messages.error(req, _('Sorry, your session has expired. Please start over and try again.'))
    return HttpResponseRedirect(base.ImportCases.get_url(domain))
