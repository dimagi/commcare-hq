import xlrd
from dimagi.utils.couch.database import get_db

def get_case_properties(domain):
    # get all unique existing case properties, known and unknown
    case_fields = []
    
    rows = get_db().view('hqcase/by_domain_action_properties',reduce=False,startkey=domain,endkey=domain).all()
    
    for row in rows:
        for field in row['value']['known']:
            if field not in case_fields:
                case_fields.append(field)

        for field in row['value']['unknown']:
            if field not in case_fields:
                case_fields.append(field)    
    
    return case_fields
    
# class to deal with Excel files
class ExcelFile(object):
    # xlrd support for .xlsx isn't complete
    ALLOWED_EXTENSIONS = ['xls']
    
    file_path = ''
    workbook = None
    column_headers = False
    
    def __init__(self, file_path, column_headers):
        self.file_path = file_path
        self.column_headers = column_headers
        
        try:
            self.workbook = xlrd.open_workbook(self.file_path)
        except:
            return None
                
    def get_first_sheet(self):
        if self.workbook:
            return self.workbook.sheet_by_index(0)
        else:
            return None
    
    def get_header_columns(self):
        sheet = self.get_first_sheet()
        
        if sheet:
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

    