from corehq.util.test_utils import generate_cases, make_make_path
from corehq.util.workbook_reading import (
    open_any_workbook,
    open_csv_workbook,
    open_xls_workbook,
    open_xlsx_workbook,
)

_make_path = make_make_path(__file__)


def get_file(name, ext):
    return _make_path('files', ext, '{}.{}'.format(name, ext))


csv_cases = [
    (open_csv_workbook, 'csv'),
    (open_any_workbook, 'csv'),
]
xls_cases = [
    (open_xls_workbook, 'xls'),
    (open_any_workbook, 'xls'),
]
xlsx_cases = [
    (open_xlsx_workbook, 'xlsx'),
    (open_any_workbook, 'xlsx'),
]
all_cases = csv_cases + xls_cases + xlsx_cases


def run_on_all_adapters(test_cls):
    return generate_cases(all_cases, test_cls)


def run_on_all_adapters_except_csv(test_cls):
    return generate_cases(xls_cases + xlsx_cases, test_cls)


def run_on_csv_adapter(test_cls):
    return generate_cases(csv_cases, test_cls)
