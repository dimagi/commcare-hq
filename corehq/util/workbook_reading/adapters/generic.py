from contextlib import contextmanager
from corehq.util.workbook_reading import SpreadsheetFileExtError
from .csv import open_csv_workbook
from .xls import open_xls_workbook
from .xlsx import open_xlsx_workbook


extensions_to_functions_dict = {
    'csv': open_csv_workbook,
    'xls': open_xls_workbook,
    'xlsx': open_xlsx_workbook,
}
valid_extensions = extensions_to_functions_dict.keys()


@contextmanager
def open_any_workbook(filename):
    """Call the relevant function from extensions_to_functions_dict, based on the filename."""
    file_has_valid_extension = False
    if '.' in filename:
        extension = filename.split('.')[-1]
        if extension in valid_extensions:
            file_has_valid_extension = True
            function_to_open_workbook = extensions_to_functions_dict[extension]
            with function_to_open_workbook(filename) as workbook:
                yield workbook

    if not file_has_valid_extension:
        error = 'File {} does not have a valid extension. Valid extensions are: {}'.format(
            filename,
            ', '.join(extensions_to_functions_dict.keys())
        )
        raise SpreadsheetFileExtError(error)
