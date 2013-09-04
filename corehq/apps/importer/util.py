import xlrd
from dimagi.utils.couch.database import get_db
from corehq.apps.importer.const import LookupErrors
from datetime import date
from casexml.apps.case.models import CommCareCase
from xlrd import xldate_as_tuple
from corehq.apps.groups.models import Group
from corehq.apps.users.models import CouchUser
from couchdbkit.exceptions import ResourceNotFound

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

class ImporterConfig(object):
    """
    Class for storing config values from the POST in a format that can
    be pickled and passed to celery tasks.
    """

    def __init__(self, request):
        self.couch_user_id = request.couch_user._id
        self.excel_fields = request.POST.getlist('excel_field[]')
        self.case_fields = request.POST.getlist('case_field[]')
        self.custom_fields = request.POST.getlist('custom_field[]')
        self.date_fields = request.POST.getlist('is_date_field[]')

        self.search_column = request.POST['search_column']

        self.key_column = request.POST['key_column']
        self.value_column = request.POST['value_column']

        self.named_columns = request.POST['named_columns']
        self.case_type = request.POST['case_type']
        self.search_field = request.POST['search_field']
        self.create_new_cases = request.POST['create_new_cases'] == 'True'

class ExcelFile(object):
    """
    Class to deal with Excel files.

    xlrd support for .xlsx isn't complete
    NOTE: other code makes the assumption that this is the only supported
    extension so if you fix this you should also fix these assumptions
    (see get_spreadsheet)
    """

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

def convert_custom_fields_to_struct(config):
    excel_fields = config.excel_fields
    case_fields = config.case_fields
    custom_fields = config.custom_fields
    date_fields = config.date_fields

    field_map = {}
    for i, field in enumerate(excel_fields):
        if field and (case_fields[i] or custom_fields[i]):
            field_map[field] = {'case': case_fields[i],
                                'custom': custom_fields[i],
                                'is_date_field': date_fields[i] == 'true'}

    return field_map

class InvalidDateException(Exception):
    pass

def parse_excel_date(date_val):
    """ Convert field value from excel to a date value """
    try:
        parsed_date = str(date(*xldate_as_tuple(date_val, 0)[:3]))
    except Exception:
        raise InvalidDateException

    return parsed_date


def convert_field_value(value):
    # coerce to string unless it's a unicode string then we want that
    if isinstance(value, unicode):
        return value
    else:
        return str(value)


def parse_search_id(config, columns, row):
    """ Find and convert the search id in an excel row """

    # Find index of user specified search column
    search_column = config.search_column
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

    return convert_field_value(search_id)

def get_key_column_index(config, columns):
    key_column = config.key_column
    try:
        key_column_index = columns.index(key_column)
    except ValueError:
        key_column_index = False

    return key_column_index

def get_value_column_index(config, columns):
    value_column = config.value_column
    try:
        value_column_index = columns.index(value_column)
    except ValueError:
        value_column_index = False

    return value_column_index

def lookup_case(search_field, search_id, domain, case_type):
    """
    Attempt to find the case in CouchDB by the provided search_field and search_id.

    Returns a tuple with case (if found) and an
    error code (if there was an error in lookup).
    """
    found = False
    if search_field == 'case_id':
        try:
            case = CommCareCase.get(search_id)

            if case.domain == domain and case.type == case_type:
                found = True
        except Exception:
            pass
    elif search_field == 'external_id':
        results = CommCareCase.view(
            'hqcase/by_domain_external_id',
            key=[domain, search_id],
            reduce=False,
            include_docs=True)
        if results:
            cases_by_type = [case for case in results
                             if case.type == case_type]

            if not cases_by_type:
                return (None, LookupErrors.NotFound)
            elif len(cases_by_type) > 1:
                return (None, LookupErrors.MultipleResults)
            else:
                case = cases_by_type[0]
                found = True

    if found:
        return (case, None)
    else:
        return (None, LookupErrors.NotFound)

def populate_updated_fields(config, columns, row):
    """
    Returns a dict map of fields that were marked to be updated
    due to the import. This can be then used to pass to the CaseBlock
    to trigger updates.
    """

    field_map = convert_custom_fields_to_struct(config)
    key_column_index = get_key_column_index(config, columns)
    value_column_index = get_value_column_index(config, columns)
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

        if update_value:
            if field_map[key]['is_date_field']:
                update_value = parse_excel_date(update_value)
            else:
                update_value = convert_field_value(update_value)

        fields_to_update[update_field_name] = update_value

    return fields_to_update

def get_spreadsheet(download_ref, column_headers=True):
    if not download_ref:
        return None
    return ExcelFile(download_ref.get_filename(), column_headers)

def is_valid_id(uploaded_id, domain, cache):
    if uploaded_id in cache:
        return cache[uploaded_id]

    # see if it's a user on this domain
    if CouchUser.get_by_user_id(uploaded_id, domain):
        return True

    # or if it is a case sharing enabled group
    try:
        group = Group.get(uploaded_id)
        return group.case_sharing
    except ResourceNotFound:
        return False
