from __future__ import absolute_import
from __future__ import unicode_literals

from corehq.apps.domain.dbaccessors import get_docs_in_domain_by_class
from corehq.apps.domain.models import Domain
from corehq.apps.userreports.util import get_indicator_adapter
from corehq.dbaccessors.couchapps.all_docs import delete_all_docs_by_doc_type
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


def delete_all_ucr_tables_for_domain(domain):
    """
    For a given domain, delete all the known UCR data source tables

    This only deletes "known" data sources for the domain.
    To identify "orphaned" tables, see the prune_old_datasources management command.
    """
    for config in get_datasources_for_domain(domain):
        adapter = get_indicator_adapter(config)
        adapter.drop_table()
