import csv
import os

from casexml.apps.case.mock import CaseBlock
from dimagi.utils.chunked import chunked

from corehq.apps.case_importer.do_import import do_import
from corehq.apps.case_importer.util import ImporterConfig, WorksheetWrapper
from corehq.apps.fixtures.models import (
    Field,
    LookupTable,
    LookupTableRow,
    TypeField,
)
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.userreports.models import StaticDataSourceConfiguration
from corehq.apps.userreports.tasks import rebuild_indicators
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.util import format_username
from corehq.form_processor.models import CommCareCase
from corehq.toggles import BULK_UPLOAD_DATE_OPENED, NAMESPACE_DOMAIN
from corehq.util.workbook_reading import make_worksheet

PATH = os.path.dirname(__file__)
FOOD_CASE_TYPE = 'food'
FOODRECALL_CASE_TYPE = 'foodrecall'


def populate_inddex_domain(domain):
    user = _get_or_create_user(domain)
    _import_cases(domain, user)
    _import_fixtures(domain)
    return _rebuild_datasource(domain)


def _get_or_create_user(domain, create=True):
    username = format_username('nick', domain)
    user = CommCareUser.get_by_username(username, strict=True)
    if not user and create:
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
    case_ids = CommCareCase.objects.get_case_ids_in_domain(domain)
    cases = CommCareCase.objects.get_cases(case_ids, domain)
    case_ids_by_external_id = {c.external_id: c.case_id for c in cases}

    case_blocks = []
    for case in cases:
        update = {}
        for k, v in case.dynamic_case_properties().items():
            if v in case_ids_by_external_id:
                update[k] = case_ids_by_external_id[v]
        if update:
            case_blocks.append(
                CaseBlock(
                    case_id=case.case_id,
                    user_id=user._id,
                    update=update,
                ).as_text()
            )

    submit_case_blocks(case_blocks, domain=domain, user_id=user._id)


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
        data_type = LookupTable(
            domain=domain,
            tag=fixture_name,
            fields=[TypeField(name=field) for field in fields],
        )
        data_type.save()

        items = (
            _mk_fixture_data_item(domain, data_type.id, fields, vals, i)
            for i, vals in enumerate(rows)
        )
        for chunk in chunked(items, 1000, list):
            LookupTableRow.objects.bulk_create(chunk)


def _mk_fixture_data_item(domain, table_id, fields, vals, i):
    return LookupTableRow(
        domain=domain,
        table_id=table_id,
        fields={name: [Field(value=val)] for name, val in zip(fields, vals)},
        item_attributes={},
        sort_key=i,
    )


def _rebuild_datasource(domain):
    config_id = StaticDataSourceConfiguration.get_doc_id(
        domain, 'food_consumption_indicators')
    rebuild_indicators(config_id, source='populate_inddex_test_domain')
    return config_id
