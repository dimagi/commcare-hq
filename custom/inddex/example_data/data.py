import csv
import os
import uuid

from corehq.apps.case_importer.do_import import do_import
from corehq.apps.case_importer.util import ImporterConfig, WorksheetWrapper
from corehq.apps.fixtures.models import (
    FixtureDataItem,
    FixtureDataType,
    FixtureTypeField,
)
from corehq.apps.userreports.models import StaticDataSourceConfiguration
from corehq.apps.userreports.tasks import rebuild_indicators
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.util import format_username
from corehq.util.couch import IterDB
from corehq.util.workbook_reading import make_worksheet

PATH = os.path.dirname(__file__)
FOOD_CASE_TYPE = 'food'
FOODRECALL_CASE_TYPE = 'foodrecall'


def populate_inddex_domain(domain):
    user = _get_or_create_user(domain)
    _import_cases(domain, FOODRECALL_CASE_TYPE, 'foodrecall_cases.csv', user)
    _import_cases(domain, FOOD_CASE_TYPE, 'food_cases.csv', user)
    _import_fixtures(domain)
    _rebuild_datasource(domain)


def _get_or_create_user(domain):
    username = format_username('nick', domain)
    user = CommCareUser.get_by_username(username)
    if not user:
        user = CommCareUser.create(domain, username, 'secret')
    return user


def _import_cases(domain, case_type, csv_filename, user):
    headers, rows = _read_csv(csv_filename)
    worksheet = WorksheetWrapper(make_worksheet([headers] + rows))
    config = _get_importer_config(case_type, headers, user._id)
    res = do_import(worksheet, config, domain)
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


def get_expected_report():
    return _read_csv('expected_result.csv')


def _import_fixtures(domain):
    for fixture_name, filename in [
            ('recipes', 'recipes.csv'),
            ('conv_factors', 'conv_factors.csv'),
            ('food_list', 'food_list.csv'),
            ('food_composition_table', 'food_composition_table.csv'),
    ]:
        fields, rows = _read_csv(filename)
        data_type = FixtureDataType(
            domain=domain,
            tag=fixture_name,
            fields=[FixtureTypeField(field_name=field) for field in fields],
        )
        data_type.save()

        with IterDB(FixtureDataItem.get_db(), chunksize=1000) as iter_db:
            for vals in rows:
                fixture_data_item = _mk_fixture_data_item(domain, data_type._id, fields, vals)
                iter_db.save(fixture_data_item)


def _mk_fixture_data_item(domain, data_type_id, fields, vals):
    """Fixtures are wicked slow, so just do it in JSON"""
    return {
        "_id": uuid.uuid4().hex,
        "doc_type": "FixtureDataItem",
        "domain": domain,
        "data_type_id": data_type_id,
        "fields": {
            field_name: {
                "doc_type": "FieldList",
                "field_list": [{
                    "doc_type": "FixtureItemField",
                    "field_value": field_value,
                    "properties": {},
                }]
            }
            for field_name, field_value in zip(fields, vals)
        },
        "item_attributes": {},
        "sort_key": 0,
    }


def _rebuild_datasource(domain):
    config_id = StaticDataSourceConfiguration.get_doc_id(
        domain, 'food_consumption_indicators')
    rebuild_indicators(config_id, source='populate_inddex_test_domain')
