import os.path
from django.http import HttpResponseRedirect
from dimagi.utils.web import render_to_response
from casexml.apps.case.models import CommCareCase, const
from casexml.apps.phone.xml import get_case_xml
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.importer import base
from corehq.apps.importer.util import ExcelFile, get_case_properties
from couchdbkit.exceptions import MultipleResultsFound, NoResultFound
from tempfile import mkstemp
from django.views.decorators.http import require_POST
from datetime import datetime, date
from xlrd import xldate_as_tuple
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import Permissions
from soil.util import expose_download
from soil import DownloadBase
from django.contrib import messages
from django.utils.translation import ugettext as _

require_can_edit_data = require_permission(Permissions.edit_data)

EXCEL_SESSION_ID = "excel_id"
MAX_ALLOWED_ROWS = 500

@require_can_edit_data
def excel_config(request, domain):
    if request.method == 'POST':
        if request.FILES:
            named_columns = request.POST['named_columns']
            uses_headers = named_columns == 'yes'
            uploaded_file_handle = request.FILES['file']
            
            extension = os.path.splitext(uploaded_file_handle.name)[1][1:].strip().lower()
            
            if extension in ExcelFile.ALLOWED_EXTENSIONS:
                # NOTE: this is kinda messy and needs to be cleaned up but
                # just trying to get something functional in place.
                # We may not always be able to reference files from subsequent
                # views if your worker changes, so we have to store it elsewhere
                # using the soil framework.
                
                # stash content in the default storage for subsequent views
                file_ref = expose_download(uploaded_file_handle.read(),
                                           expiry=1*60*60)
                request.session[EXCEL_SESSION_ID] = file_ref.download_id

                spreadsheet = _get_spreadsheet(file_ref, uses_headers)
                if not spreadsheet:
                    return _spreadsheet_expired(request, domain)
                columns = spreadsheet.get_header_columns()
                row_count = spreadsheet.get_num_rows()
                if row_count > MAX_ALLOWED_ROWS:
                    messages.error(request, _('Sorry, your spreadsheet is too big. '
                                              'Please reduce the number of '
                                              'rows to less than %s and try again') % MAX_ALLOWED_ROWS)
                else:
                    # get case types in this domain
                    case_types = []
                    for row in CommCareCase.view('hqcase/types_by_domain',reduce=True,group=True,startkey=[domain],endkey=[domain,{}]).all():
                        if not row['key'][1] in case_types:
                            case_types.append(row['key'][1])

                    if len(case_types) > 0:
                        return render_to_response(request, "importer/excel_config.html", {
                                                    'named_columns': named_columns, 
                                                    'columns': columns,
                                                    'case_types': case_types,
                                                    'domain': domain,
                                                    'report': {
                                                        'name': 'Import: Configuration'
                                                     },
                                                    'slug': base.ImportCases.slug})
                    else:
                        messages.error(request, _('No cases have been submitted to this domain. '
                                                  'You cannot update case details from an Excel '
                                                  'file until you have existing cases.'))
            else:
                messages.error(request, _('The Excel file you chose could not be processed. '
                                          'Please check that it is saved as a Microsoft Excel '
                                          '97/2000 .xls file.'))
        else:
            messages.error(request, _('Please choose an Excel file to import.'))
    #TODO show bad/invalid file error on this page
    return HttpResponseRedirect(base.ImportCases.get_url(domain=domain))

      
@require_POST
@require_can_edit_data
def excel_fields(request, domain):
    named_columns = request.POST['named_columns']
    uses_headers = named_columns == 'yes'
    case_type = request.POST['case_type']
    search_column = request.POST['search_column']
    search_field = request.POST['search_field']
    key_value_columns = request.POST['key_value_columns']
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
                  
    case_fields = get_case_properties(domain, case_type)
    
    # hide search column and matching case fields from the update list
    try:    
        excel_fields.remove(search_column)
    except:
        pass
    
    try:    
        case_fields.remove(search_field)
    except:
        pass                    
    
    return render_to_response(request, "importer/excel_fields.html", {
                                'named_columns': named_columns,
                                'case_type': case_type,                                                               
                                'search_column': search_column, 
                                'search_field': search_field,                                                        
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
    named_columns = request.POST['named_columns']
    uses_headers = named_columns == 'yes'
    case_type = request.POST['case_type']
    search_column = request.POST['search_column']
    search_field = request.POST['search_field']
    key_column = request.POST['key_column']
    value_column = request.POST['value_column']
    
    # TODO musn't be able to select an excel_field twice (in html)
    excel_fields = request.POST.getlist('excel_field[]')
    case_fields = request.POST.getlist('case_field[]')
    custom_fields = request.POST.getlist('custom_field[]')
    date_yesno = request.POST.getlist('date_yesno[]')

    # turn all the select boxes into a useful struct
    field_map = {}
    for i, field in enumerate(excel_fields):
        if field and (case_fields[i] or custom_fields[i]):
            field_map[field] = {'case': case_fields[i], 'custom': custom_fields[i], 'date': int(date_yesno[i])}
        
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
    
    # find indexes of user selected columns
    search_column_index = columns.index(search_column)
    
    try:
        key_column_index = columns.index(key_column)
    except ValueError:
        key_column_index = False
    
    try:
        value_column_index = columns.index(value_column)
    except ValueError:
        value_column_index = False

    no_match_count = 0
    match_count = 0
    too_many_matches = 0
    
    cases = {}
   
    # start looping through all the rows
    for i in range(spreadsheet.get_num_rows()):
        # skip first row if it is a header field
        if i == 0 and named_columns:
            continue
        
        row = spreadsheet.get_row(i)
        found = False
        
        search_id = row[search_column_index]

        # see what has come out of the spreadsheet
        try:
            float(search_id)
            # no error, so something that looks like a number came out of the cell
            # in which case we should remove any decimal places
            search_id = int(search_id)
        except ValueError:
            # error, so probably a string
            pass
        
        # couchdb wants a string 
        search_id = str(search_id)    
                
        if search_field == 'case_id':
            try:
                case = CommCareCase.get(search_id)
                if case.domain == domain:
                    found = True
            except Exception:
                pass
        elif search_field == 'external_id':
            try:
                case = CommCareCase.view('hqcase/by_domain_external_id', 
                                         key=[domain, search_id], 
                                         reduce=False, 
                                         include_docs=True).one()
                found = True if case else False
            except NoResultFound:
                pass
            except MultipleResultsFound:
                too_many_matches += 1     
               
        if found:
            match_count += 1
        else:
            no_match_count += 1
            continue
        
        # here be monsters
        fields_to_update = {}
        
        for key in field_map:          
            update_value = False
            
            if key_column_index and key == row[key_column_index]:
                update_value = row[value_column_index]
            else:                
                # nothing was set so maybe it is a regular column
                try:
                    update_value = row[columns.index(key)]
                except Exception:
                    pass
            
            if update_value:
                # case field to update
                if field_map[key]['custom']:
                    # custom (new) field was entered
                    update_field_name = field_map[key]['custom']
                else:
                    # existing case field was chosen
                    update_field_name = field_map[key]['case']
                
                if field_map[key]['date'] == 1:
                    update_value = date(*xldate_as_tuple(update_value, 0)[:3])
                                    
                fields_to_update[update_field_name] = update_value
    
        if case.type == case_type:      
            if cases.has_key(search_id):
                cases[search_id]['fields'].update(fields_to_update)
            else:
                cases[search_id] = {'obj': case, 'fields': fields_to_update}
            
    # run updates
    for id, case in cases.iteritems():
        for name, value in case['fields'].iteritems():
            case['obj'].set_case_property(name, value)
                                               
        case['obj'].modified_on = datetime.utcnow()
                
        # spoof case update xform submission
        case_block = get_case_xml(case['obj'], (const.CASE_ACTION_UPDATE,), version='2.0')
        submit_case_blocks(case_block, domain)
            
    # unset filename session var
    try:
        del request.session[EXCEL_SESSION_ID]
    except KeyError:
        pass            
    
    return render_to_response(request, "importer/excel_commit.html", {
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
