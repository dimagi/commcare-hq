import xlrd
from dimagi.utils.couch.database import get_db
from corehq.apps.importer.const import LookupErrors
from xml.etree import ElementTree
from dimagi.utils.parsing import json_format_datetime
from datetime import date
from corehq.apps.hqcase.utils import submit_case_blocks
from casexml.apps.case.models import CommCareCase
from xlrd import xldate_as_tuple

def get_case_properties(domain, case_type=None):
    """
    For a given case type and domain, get all unique existing case properties,
    known and unknown
    """
    key = [domain]
    if case_type:
        key.append(case_type)
    rows = get_db().view('hqcase/all_case_properties',
                         startkey=key,
                         endkey=key + [{}],
                         reduce=True, group=True, group_level=3).all()
    return sorted(set([r['key'][2] for r in rows]))

# class to deal with Excel files
class ExcelFile(object):
    # xlrd support for .xlsx isn't complete
    # NOTE: other code makes the assumption that this is the only supported
    # extension so if you fix this you should also fix these assumptions
    # (see _get_spreadsheet in views.py)
    ALLOWED_EXTENSIONS = ['xls']

    file_path = ''
    workbook = None
    column_headers = False
    has_errors = False

    def __init__(self, file_path, column_headers):
        self.file_path = file_path
        self.column_headers = column_headers

        try:
            self.workbook = xlrd.open_workbook(self.file_path)
        except Exception:
            self.has_errors = True

    def get_first_sheet(self):
        if self.workbook:
            return self.workbook.sheet_by_index(0)
        else:
            return None

    def get_header_columns(self):
        sheet = self.get_first_sheet()

        if sheet and sheet.ncols > 0:
            columns = []

            # get columns
            if self.column_headers:
                columns = sheet.row_values(0)
            else:
                for colnum in range(sheet.ncols):
                    columns.append("Column %i" % (colnum,))

            return columns
        else:
            return []

    def get_column_values(self, column_index):
        sheet = self.get_first_sheet()

        if sheet:
            if self.column_headers:
                return sheet.col_values(column_index)[1:]
            else:
                return sheet.col_values(column_index)
        else:
            return []

    def get_unique_column_values(self, column_index):
        return list(set(self.get_column_values(column_index)))

    def get_num_rows(self):
        sheet = self.get_first_sheet()

        if sheet:
            return sheet.nrows

    def get_row(self, index):
        sheet = self.get_first_sheet()

        if sheet:
            return sheet.row_values(index)

def convert_custom_fields_to_struct(request):
    excel_fields = request.POST.getlist('excel_field[]')
    case_fields = request.POST.getlist('case_field[]')
    custom_fields = request.POST.getlist('custom_field[]')
    date_field = request.POST.getlist('is_date_field[]')

    field_map = {}
    for i, field in enumerate(excel_fields):
        if field and (case_fields[i] or custom_fields[i]):
            field_map[field] = {'case': case_fields[i],
                                'custom': custom_fields[i],
                                'is_date_field': date_field[i] == 'true'}

    return field_map

def parse_excel_date(date_val):
    """ Convert field value from excel to a date value """
    return str(date(*xldate_as_tuple(date_val, 0)[:3]))

def parse_search_id(request, columns, row):
    """ Find and convert the search id in an excel row """

    # Find index of user specified search column
    search_column = request.POST['search_column']
    search_column_index = columns.index(search_column)

    search_id = row[search_column_index]
    try:
        # if the spreadsheet gives a number, strip any decimals off
        # float(x) is more lenient in conversion from string so both
        # are used
        search_id = int(float(search_id))
    except ValueError:
        # if it's not a number that's okay too
        pass

    # need a string no matter what the type was
    return str(search_id)

def submit_case_block(caseblock, domain, username, user_id):
    """ Convert a CaseBlock object to xml and submit for creation/update """
    casexml = ElementTree.tostring(caseblock.as_xml(format_datetime=json_format_datetime))
    submit_case_blocks(casexml, domain, username, user_id)

def get_key_column_index(request, columns):
    key_column = request.POST['key_column']
    try:
        key_column_index = columns.index(key_column)
    except ValueError:
        key_column_index = False

    return key_column_index

def get_value_column_index(request, columns):
    value_column = request.POST['value_column']
    try:
        value_column_index = columns.index(value_column)
    except ValueError:
        value_column_index = False

    return value_column_index

def lookup_case(search_field, search_id, domain):
    """
    Attempt to find the case in CouchDB by the provided search_field and search_id.

    Returns a tuple with case (if found) and an
    error code (if there was an error in lookup).
    """
    found = False
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
            found = bool(case)
        except NoResultFound:
            pass
        except MultipleResultsFound:
            return (None, LookupErrors.MultipleResults)

    if found:
        return (case, None)
    else:
        return (None, LookupErrors.NotFound)

def populate_updated_fields(request, columns, row):
    """
    Returns a dict map of fields that were marked to be updated
    due to the import. This can be then used to pass to the CaseBlock
    to trigger updates.
    """

    field_map = convert_custom_fields_to_struct(request)
    key_column_index = get_key_column_index(request, columns)
    value_column_index = get_value_column_index(request, columns)
    fields_to_update = {}

    for key in field_map:
        try:
            if key_column_index and key == row[key_column_index]:
                update_value = row[value_column_index]
            else:
                update_value = row[columns.index(key)]
        except:
            continue

        if field_map[key]['custom']:
            # custom (new) field was entered
            update_field_name = field_map[key]['custom']
        else:
            # existing case field was chosen
            update_field_name = field_map[key]['case']

        if update_value and field_map[key]['is_date_field']:
            update_value = parse_excel_date(update_value)

        fields_to_update[update_field_name] = update_value

    return fields_to_update
