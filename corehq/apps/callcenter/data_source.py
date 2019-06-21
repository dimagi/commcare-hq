from __future__ import absolute_import
from __future__ import unicode_literals
import json
import os
from collections import namedtuple
from copy import deepcopy

import settings
from corehq.apps.callcenter.utils import get_call_center_domains
from corehq.apps.userreports.models import StaticDataSourceConfiguration
from io import open

MODULE_PATH = os.path.dirname(__file__)
DATA_SOURCES_PATH = os.path.join(MODULE_PATH, 'data_sources')
FORM_DATA_SOURCE_PATH = os.path.join(DATA_SOURCES_PATH, 'call_center_forms.json')
CASE_DATA_SOURCE_PATH = os.path.join(DATA_SOURCES_PATH, 'call_center_cases.json')
CASE_ACTION_DATA_SOURCE_PATH = os.path.join(DATA_SOURCES_PATH, 'call_center_case_actions.json')
TABLE_IDS = {
    'forms': 'cc_forms',
    'cases': 'cc_cases',
    'case_actions': 'cc_case_actions'
}

CallCenterReportDataSources = namedtuple('CallCenterReportDataSources', 'forms, cases, case_actions')


def call_center_data_source_configuration_provider():
    domains = [domain for domain in get_call_center_domains() if domain.use_fixtures]
    if not domains:
        return

    def _get_ds(ds_domains, data_source_path):
        data_source_json = _get_json(data_source_path)
        data_source_json['domains'] = ds_domains
        data_source_json['server_environment'] = [settings.SERVER_ENVIRONMENT]
        ds_conf = StaticDataSourceConfiguration.wrap(deepcopy(data_source_json))
        return ds_conf, data_source_path

    form_ds_domains = [domain.name for domain in domains if domain.form_datasource_enabled]
    case_ds_domains = [domain.name for domain in domains if domain.case_datasource_enabled]
    case_actions_ds_domains = [domain.name for domain in domains if domain.case_actions_datasource_enabled]
    if form_ds_domains:
        yield _get_ds(form_ds_domains, FORM_DATA_SOURCE_PATH)
    if case_ds_domains:
        yield _get_ds(case_ds_domains, CASE_DATA_SOURCE_PATH)
    if case_actions_ds_domains:
        yield _get_ds(case_actions_ds_domains, CASE_ACTION_DATA_SOURCE_PATH)


def get_data_source_templates():
    configs_json = [
        _get_json(FORM_DATA_SOURCE_PATH),
        _get_json(CASE_DATA_SOURCE_PATH),
        _get_json(CASE_ACTION_DATA_SOURCE_PATH),
    ]
    return [config['config'] for config in configs_json]


def get_sql_adapters_for_domain(domain_name):
    forms, cases, case_actions = get_data_source_templates()
    return CallCenterReportDataSources(
        forms=_get_sql_adapter(domain_name, forms),
        cases=_get_sql_adapter(domain_name, cases),
        case_actions=_get_sql_adapter(domain_name, case_actions),
    )


def _get_sql_adapter(domain_name, data_source_json):
    from corehq.apps.userreports.util import get_indicator_adapter
    data_source = _make_data_source_for_domain(data_source_json, domain_name)
    return get_indicator_adapter(data_source, load_source='callcenter')


def _make_data_source_for_domain(data_source_json, domain_name):
    from corehq.apps.userreports.models import StaticDataSourceConfiguration
    from corehq.apps.userreports.models import DataSourceConfiguration

    doc = deepcopy(data_source_json)
    doc['domain'] = domain_name
    doc['_id'] = StaticDataSourceConfiguration.get_doc_id(domain_name, doc['table_id'])
    return DataSourceConfiguration.wrap(doc)


def _get_json(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)
