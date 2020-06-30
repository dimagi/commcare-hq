import csv
import os
import uuid

from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.util import post_case_blocks

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
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.toggles import BULK_UPLOAD_DATE_OPENED, NAMESPACE_DOMAIN
from corehq.util.couch import IterDB
from corehq.util.workbook_reading import make_worksheet

PATH = os.path.dirname(__file__)
FOOD_CASE_TYPE = 'food'
FOODRECALL_CASE_TYPE = 'foodrecall'


def populate_inddex_domain(domain):
    user = _get_or_create_user(domain)
    _import_cases(domain, user)
    _import_fixtures(domain)
    _rebuild_datasource(domain)


def _get_or_create_user(domain):
    username = format_username('nick', domain)
    user = CommCareUser.get_by_username(username, strict=True)
    if not user:
        user = CommCareUser.create(domain, username, 'secret', None, None)
    return user


def _import_cases(domain, user):
    BULK_UPLOAD_DATE_OPENED.set(domain, True, NAMESPACE_DOMAIN)
    _import_case_type(domain, FOODRECALL_CASE_TYPE, 'foodrecall_cases.csv', user)
    _import_case_type(domain, FOOD_CASE_TYPE, 'food_cases.csv', user)
    BULK_UPLOAD_DATE_OPENED.set(domain, False, NAMESPACE_DOMAIN)
    _update_case_id_properties(domain, user)


def _import_case_type(domain, case_type, csv_filename, user):
    headers, rows = _read_csv(csv_filename)
    worksheet = WorksheetWrapper(make_worksheet([headers] + rows))
    config = _get_importer_config(case_type, headers, user._id)
    res = do_import(worksheet, config, domain)
    if res['errors']:
        raise Exception(res)


def _update_case_id_properties(domain, user):
    """Some case properties store the ID of related cases.  This updates those IDs"""

    accessor = CaseAccessors(domain)
    case_ids = accessor.get_case_ids_in_domain()
    cases = list(accessor.get_cases(case_ids))
    case_ids_by_external_id = {c.external_id: c.case_id for c in cases}

    case_blocks = []
    for case in cases:
        update = {}
        for k, v in case.dynamic_case_properties().items():
            if v in case_ids_by_external_id:
                update[k] = case_ids_by_external_id[v]
        if update:
            case_blocks.append(
                CaseBlock.deprecated_init(
                    case_id=case.case_id,
                    user_id=user._id,
                    update=update,
                ).as_xml()
            )

    post_case_blocks(case_blocks, domain=domain, user_id=user._id)


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


def _import_fixtures(domain):
    for fixture_name, filename in [
            ('recipes', 'recipes.csv'),
            ('conv_factors', 'conv_factors.csv'),
            ('food_list', 'food_list.csv'),
            ('food_composition_table', 'food_composition_table.csv'),
            ('nutrients_lookup', 'nutrients_lookup.csv'),
            ('languages', 'languages.csv'),
    ]:
        fields, rows = _read_csv(filename)
        data_type = FixtureDataType(
            domain=domain,
            tag=fixture_name,
            fields=[FixtureTypeField(field_name=field) for field in fields],
        )
        data_type.save()

        with IterDB(FixtureDataItem.get_db(), chunksize=1000) as iter_db:
            for i, vals in enumerate(rows):
                fixture_data_item = _mk_fixture_data_item(domain, data_type._id, fields, vals, i)
                iter_db.save(fixture_data_item)


def _mk_fixture_data_item(domain, data_type_id, fields, vals, i):
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
        "sort_key": i,
    }


def _rebuild_datasource(domain):
    config_id = StaticDataSourceConfiguration.get_doc_id(
        domain, 'food_consumption_indicators')
    rebuild_indicators(config_id, source='populate_inddex_test_domain')
