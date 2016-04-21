import json
import os
from collections import namedtuple
from copy import deepcopy

from corehq.apps.callcenter.utils import get_call_center_domains

MODULE_PATH = os.path.dirname(__file__)
DATA_SOURCES_PATH = os.path.join(MODULE_PATH, 'data_sources')
FORM_DATA_SOURCE_PATH = os.path.join(DATA_SOURCES_PATH, 'call_center_forms.json')
CASE_DATA_SOURCE_PATH = os.path.join(DATA_SOURCES_PATH, 'call_center_cases.json')
CASE_ACTION_DATA_SOURCE_PATH = os.path.join(DATA_SOURCES_PATH, 'call_center_case_actions.json')

CallCenterReportDataSources = namedtuple('CallCenterReportDataSources', 'forms, cases, case_actions')


def call_center_data_source_provider():
    call_center_data_sources = get_data_source_templates()

    for domain in get_call_center_domains():
        if domain.use_fixtures:
            for data_source_json in call_center_data_sources:
                yield _make_data_source_for_domain(data_source_json, domain.name)


def get_data_source_templates():
    call_center_data_sources = [
        _get_json(FORM_DATA_SOURCE_PATH),
        _get_json(CASE_DATA_SOURCE_PATH),
        _get_json(CASE_ACTION_DATA_SOURCE_PATH),
    ]
    return call_center_data_sources


def get_sql_adapters_for_domain(domain_name):
    forms, cases, case_actions = get_data_source_templates()
    return CallCenterReportDataSources(
        forms=_get_sql_adapter(domain_name, forms),
        cases=_get_sql_adapter(domain_name, cases),
        case_actions=_get_sql_adapter(domain_name, case_actions),
    )


def _get_sql_adapter(domain_name, data_source_json):
    from corehq.apps.userreports.sql import IndicatorSqlAdapter
    data_source = _make_data_source_for_domain(data_source_json, domain_name)
    return IndicatorSqlAdapter(data_source)


def _make_data_source_for_domain(data_source_json, domain_name):
    from corehq.apps.userreports.models import StaticDataSourceConfiguration
    from corehq.apps.userreports.models import DataSourceConfiguration

    doc = deepcopy(data_source_json)
    doc['domain'] = domain_name
    doc['_id'] = StaticDataSourceConfiguration.get_doc_id(domain_name, doc['table_id'])
    return DataSourceConfiguration.wrap(doc)


def _get_json(path):
    with open(path) as f:
        return json.load(f)
