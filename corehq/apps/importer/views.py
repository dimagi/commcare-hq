import uuid
import os.path
from django.http import HttpResponseRedirect, HttpResponse, HttpResponseBadRequest, Http404, HttpResponseNotFound
from django.core.urlresolvers import reverse
from dimagi.utils.web import render_to_response
from casexml.apps.case.models import CommCareCase, CommCareCaseAction, const
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.importer import base
from corehq.apps.importer.util import ExcelFile
from tempfile import mkstemp
from datetime import datetime

@login_and_domain_required
def excel_config(request, domain):
    error_type = "nofile"
    
    if request.method == 'POST' and request.FILES:
        named_columns = request.POST['named_columns']    
        uploaded_file_handle = request.FILES['file']
        
        extension = os.path.splitext(uploaded_file_handle.name)[1][1:].strip().lower()
        
        if extension in ExcelFile.ALLOWED_EXTENSIONS and uploaded_file_handle.content_type == 'application/vnd.ms-excel':
            # get a temp file
            fd, filename = mkstemp(suffix='.'+extension)
            
            with os.fdopen(fd, "wb") as destination:
                # write the uploaded file to the temp file
                for chunk in uploaded_file_handle.chunks():
                    destination.write(chunk)

            uploaded_file_handle.close() 
            
            # stash filename for subsequent views      
            request.session['excel_path'] = filename  
            
            # open spreadsheet and get columns
            spreadsheet = ExcelFile(filename, (named_columns == 'yes'))
            columns = spreadsheet.get_header_columns()
                
            # get case types in this domain
            case_types = []
            for row in CommCareCase.view('hqcase/types_by_domain',reduce=True,group=True,startkey=[domain],endkey=[domain,{}]).all():
                if not row['key'][1] in case_types:
                    case_types.append(row['key'][1])
                    
            if len(case_types) > 0:                                                
                return render_to_response(request, "excel_config.html", {
                                            'named_columns': named_columns, 
                                            'columns': columns,
                                            'case_types': case_types,
                                            'domain': domain,
                                            'report': {
                                                'name': 'Import: Configuration'
                                             },
                                            'slug': base.ExcelImporter.slug})
            else:
                error_type = "cases"
        else:
            error_type = "file"
    
    #TODO show bad/invalid file error on this page
    return HttpResponseRedirect(reverse("report_dispatcher", args=[domain, base.ExcelImporter.slug]) + "?error=" + error_type)
      
@login_and_domain_required
def excel_fields(request, domain):
    named_columns = request.POST['named_columns']
    filename = request.session.get('excel_path')
    case_type = request.POST['case_type']
    search_column = request.POST['search_column']
    search_field = request.POST['search_field']
    key_value_columns = request.POST['key_value_columns']
    key_column = ''
    value_column = ''
    
    spreadsheet = ExcelFile(filename, named_columns)
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
        excel_fields.remove(value_column)                 
    else:
        excel_fields = columns
              
    # get all unique existing case properties, known and unknown
    # TODO limit to case type
    case_fields = []
    row = CommCareCase.view('hqcase/unique_known_properties',reduce=True,group=True,startkey=domain,endkey=domain).one()
    for value in row['value']:
        case_fields.append(value)
        
    row = CommCareCase.view('hqcase/unique_unknown_properties',reduce=True,group=True,startkey=domain,endkey=domain).one()
    for value in row['value']:
        case_fields.append(value)       
    
    # hide search column and matching case fields from the update list
    try:    
        excel_fields.remove(search_column)
    except:
        pass
    
    try:    
        case_fields.remove(search_field)
    except:
        pass                    
    
    return render_to_response(request, "excel_fields.html", {
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
                                'slug': base.ExcelImporter.slug})     

@login_and_domain_required
def excel_commit(request, domain):  
    named_columns = request.POST['named_columns'] 
    filename = request.session.get('excel_path')
    case_type = request.POST['case_type']
    search_column = request.POST['search_column']
    search_field = request.POST['search_field']
    key_column = request.POST['key_column']
    value_column = request.POST['value_column']    
    
    # get all unique existing case properties, known and unknown
    known_properties = []
    row = CommCareCase.view('hqcase/unique_known_properties',reduce=True,group=True,startkey=domain,endkey=domain).one()
    for value in row['value']:
        known_properties.append(value)
        
    unknown_properties = []
    row = CommCareCase.view('hqcase/unique_unknown_properties',reduce=True,group=True,startkey=domain,endkey=domain).one()
    for value in row['value']:
        unknown_properties.append(value)     
    
    # TODO musn't be able to select an excel_field twice (in html)
    excel_fields = request.POST.getlist('excel_field[]')
    case_fields = request.POST.getlist('case_field[]')
    custom_fields = request.POST.getlist('custom_field[]')

    # turn all the select boxes into a useful struct
    field_map = {}
    for i, field in enumerate(excel_fields):
        if field and (case_fields[i] or custom_fields[i]):
            field_map[field] = {'case': case_fields[i], 'custom': custom_fields[i]}
        
    spreadsheet = ExcelFile(filename, named_columns)
    columns = spreadsheet.get_header_columns()        
    
    # find indexes of user selected columns
    search_column_index = columns.index(search_column)
    
    try:
        key_column_index = columns.index(key_column)
    except:
        key_column_index = False
    
    try:
        value_column_index = columns.index(value_column)
    except:
        value_column_index = False

    no_match_count = 0
    match_count = 0
    
    cases = {}
   
    # start looping through all the rows
    for i in range(spreadsheet.get_num_rows()):
        # skip first row if it is a header field
        if i == 0 and named_columns:
            continue
        
        row = spreadsheet.get_row(i)
        found = False
                
        if search_field == 'case_id':
            try:
                case = CommCareCase.get(row[search_column_index])
                if case.domain == domain:
                    found = True
            except:
                pass
        elif search_field == 'external_id':
            search_result = CommCareCase.view('hqcase/by_domain_external_id', 
                                              startkey=[domain, row[search_column_index]], 
                                              endkey=[domain, row[search_column_index]]
                                              ).one()
            try:
                case = CommCareCase.get(search_result['id'])
                found = True       
            except:
                pass

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
                except:
                    pass
            
            if update_value:
                # case field to update
                if field_map[key]['custom']:
                    # custom (new) field was entered
                    update_field_name = field_map[key]['custom']
                else:
                    # existing case field was chosen
                    update_field_name = field_map[key]['case']
                
                fields_to_update[update_field_name] = update_value
    
        if case.type == case_type:      
            if cases.has_key(row[search_column_index]):
                cases[row[search_column_index]]['fields'].update(fields_to_update)
            else:
                cases[row[search_column_index]] = {'obj': case, 'fields': fields_to_update}
            
    # run db updates
    for id, case in cases.iteritems():
        update_action = CommCareCaseAction()
        update_action.action_type = const.CASE_ACTION_UPDATE
        update_action.date = datetime.utcnow() # date field in spreadsheet if exists?
        update_action.server_date = datetime.utcnow()
                    
        for name, value in case['fields'].iteritems():
            case['obj'].set_case_property(name, value)
            
            if name in known_properties:
                update_action.updated_known_properties[name] = value
            else:
                update_action.updated_unknown_properties[name] = value
                                               
        case['obj'].actions.append(update_action)
        case['obj'].modified_on = datetime.utcnow()
        case['obj'].save()        
            
    # unset filename session var
    try:
        del request.session['excel_path']
    except KeyError:
        pass            
    
    return render_to_response(request, "excel_commit.html", {
                                'match_count': match_count,
                                'no_match_count': no_match_count,
                                'domain': domain,
                                'report': {
                                    'name': 'Import: Completed'
                                 },
                                'slug': base.ExcelImporter.slug})    
     