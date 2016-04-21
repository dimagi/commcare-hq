import json
import os
from copy import deepcopy

from corehq.apps.callcenter.utils import get_call_center_domains

MODULE_PATH = os.path.dirname(__file__)
DATA_SOURCES_PATH = os.path.join(MODULE_PATH, 'data_sources')
FORM_DATA_SOURCE_PATH = os.path.join(DATA_SOURCES_PATH, 'call_center_forms.json')
CASE_DATA_SOURCE_PATH = os.path.join(DATA_SOURCES_PATH, 'call_center_cases.json')
CASE_ACTION_DATA_SOURCE_PATH = os.path.join(DATA_SOURCES_PATH, 'call_center_case_actions.json')


def call_center_data_source_provider():
    call_center_data_sources = [
        _get_datasource_json(FORM_DATA_SOURCE_PATH),
        _get_datasource_json(CASE_DATA_SOURCE_PATH),
        _get_datasource_json(CASE_ACTION_DATA_SOURCE_PATH),
    ]

    for domain in get_call_center_domains():
        if domain.use_fixtures:
            for data_source_json in call_center_data_sources:
                yield _make_data_source_for_domain(data_source_json, domain)


def _make_data_source_for_domain(data_source_json, domain_lite):
    from corehq.apps.userreports.models import StaticDataSourceConfiguration
    from corehq.apps.userreports.models import DataSourceConfiguration

    doc = deepcopy(data_source_json)
    doc['domain'] = domain_lite.name
    doc['_id'] = StaticDataSourceConfiguration.get_doc_id(domain_lite.name, doc['table_id'])
    return DataSourceConfiguration.wrap(doc)


def _get_datasource_json(path):
    with open(path) as f:
        return json.load(f)
