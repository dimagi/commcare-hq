from __future__ import absolute_import
from __future__ import unicode_literals

import re

from corehq.apps.domain.dbaccessors import get_docs_in_domain_by_class
from corehq.apps.domain.models import Domain
from corehq.apps.userreports.util import get_legacy_table_name, get_table_name
from corehq.dbaccessors.couchapps.all_docs import delete_all_docs_by_doc_type
from corehq.sql_db.connections import connection_manager, UCR_ENGINE_ID
from corehq.util.test_utils import unit_testing_only


def get_number_of_report_configs_by_data_source(domain, data_source_id):
    """
    Return the number of report configurations that use the given data source.
    """
    from corehq.apps.userreports.models import ReportConfiguration
    return ReportConfiguration.view(
        'userreports/report_configs_by_data_source',
        reduce=True,
        key=[domain, data_source_id]
    ).one()['value']


def get_report_configs_for_domain(domain):
    from corehq.apps.userreports.models import ReportConfiguration
    return sorted(
        get_docs_in_domain_by_class(domain, ReportConfiguration),
        key=lambda report: report.title or '',
    )


def get_datasources_for_domain(domain, referenced_doc_type=None, include_static=False, include_aggregate=False):
    from corehq.apps.userreports.models import DataSourceConfiguration, StaticDataSourceConfiguration
    key = [domain]
    if referenced_doc_type:
        key.append(referenced_doc_type)
    datasources = sorted(
        DataSourceConfiguration.view(
            'userreports/data_sources_by_build_info',
            startkey=key,
            endkey=key + [{}],
            reduce=False,
            include_docs=True
        ),
        key=lambda config: config.display_name or '')

    if include_static:
        static_ds = StaticDataSourceConfiguration.by_domain(domain)
        if referenced_doc_type:
            static_ds = [ds for ds in static_ds if ds.referenced_doc_type == referenced_doc_type]
        datasources.extend(sorted(static_ds, key=lambda config: config.display_name))

    if include_aggregate:
        from corehq.apps.aggregate_ucrs.models import AggregateTableDefinition
        datasources.extend(AggregateTableDefinition.objects.filter(domain=domain).all())
    return datasources


@unit_testing_only
def get_all_report_configs():
    all_domains = Domain.get_all()
    for domain_obj in all_domains:
        for report_config in get_report_configs_for_domain(domain_obj.name):
            yield report_config


@unit_testing_only
def delete_all_report_configs():
    from corehq.apps.userreports.models import ReportConfiguration
    delete_all_docs_by_doc_type(ReportConfiguration.get_db(), ('ReportConfiguration',))


def get_all_table_names_for_domain(domain):
    engine = connection_manager.get_engine(UCR_ENGINE_ID)
    with engine.begin() as connection:
        possible_matches = connection.execute("select tablename from pg_tables where tablename ~ %s", domain)
    # DO NOT assume just because the domain is in the table name
    # that the table is in the domain
    all_table_names_for_domain = []
    for table_name, in possible_matches:
        match = re.match(r'^(config_report|ucr)_(.*)_([0-9a-f]{0,29})_([0-9a-f]{8})$', table_name)
        if match:
            prefix, table_domain, table_big_hash, table_little_hash = match.groups()
            if prefix == 'ucr':
                table_name_check = get_table_name(domain, table_big_hash)
            else:
                table_name_check = get_legacy_table_name(domain, table_big_hash)
            if table_name == table_name_check:
                all_table_names_for_domain.append(table_name)
    return all_table_names_for_domain


def delete_all_ucr_tables_for_domain(domain):
    engine = connection_manager.get_engine(UCR_ENGINE_ID)
    with engine.begin() as connection:
        for table_name in get_all_table_names_for_domain(domain):
            connection.execute('DROP TABLE "{}"'.format(table_name))
