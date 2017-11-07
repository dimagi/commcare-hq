from __future__ import absolute_import
from corehq.util.workbook_reading import open_xls_workbook, open_xlsx_workbook, \
    open_any_workbook
from corehq.util.test_utils import generate_cases, make_make_path

_make_path = make_make_path(__file__)


def get_file(name, ext):
    return _make_path('files', ext, '{}.{}'.format(name, ext))


def run_on_all_adapters(test_cls):
    return generate_cases([
        (open_xls_workbook, 'xls'),
        (open_xlsx_workbook, 'xlsx'),
        (open_any_workbook, 'xls'),
        (open_any_workbook, 'xlsx'),
    ], test_cls)
