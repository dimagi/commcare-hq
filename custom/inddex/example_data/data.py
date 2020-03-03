import csv
import os

from corehq.apps.case_importer.do_import import do_import
from corehq.apps.case_importer.util import ImporterConfig, WorksheetWrapper
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.util import format_username
from corehq.util.workbook_reading import make_worksheet

PATH = os.path.dirname(__file__)
INDDEX_DOMAIN = 'inddex-reports'
FOOD_CASE_TYPE = 'food'
FOODRECALL_CASE_TYPE = 'foodrecall'


def import_data():
    user = _make_user()
    _import_cases(FOODRECALL_CASE_TYPE, 'foodrecall_cases.csv', user)
    _import_cases(FOOD_CASE_TYPE, 'food_cases.csv', user)


def _make_user():
    username = format_username('nick', INDDEX_DOMAIN)
    return CommCareUser.create(INDDEX_DOMAIN, username, 'secret')


def _import_cases(case_type, csv_filename, user):
    headers, rows = _read_csv(csv_filename)
    worksheet = WorksheetWrapper(make_worksheet([headers] + rows))
    config = _get_importer_config(case_type, headers, user._id)
    res = do_import(worksheet, config, INDDEX_DOMAIN)
    if res['errors']:
        raise Exception(res)


def _read_csv(filename):
    with open(os.path.join(PATH, filename)) as f:
        reader = csv.reader(f)
        headers = next(reader)
        rows = list(reader)
        return headers, rows


def _get_importer_config(case_type, headers, user_id):
    return ImporterConfig(
        couch_user_id=user_id,
        case_type=case_type,
        excel_fields=headers,
        case_fields=[''] * len(headers),
        custom_fields=headers,
        search_column=headers[0],
        search_field='external_id',
        create_new_cases=True,
    )
