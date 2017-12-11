from __future__ import absolute_import
from corehq.apps.domain.dbaccessors import get_docs_in_domain_by_class
from corehq.apps.domain.models import Domain
from corehq.apps.userreports.const import UCR_ES_BACKEND, UCR_LABORATORY_BACKEND, UCR_ES_PRIMARY
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
        key=lambda report: report.title,
    )


def get_datasources_for_domain(domain, referenced_doc_type=None):
    from corehq.apps.userreports.models import DataSourceConfiguration
    key = [domain]
    if referenced_doc_type:
        key.append(referenced_doc_type)
    return sorted(
        DataSourceConfiguration.view(
            'userreports/data_sources_by_build_info',
            start_key=key,
            end_key=key + [{}],
            reduce=False,
            include_docs=True
        ),
        key=lambda config: config.display_name
    )


@unit_testing_only
def get_all_report_configs():
    all_domains = Domain.get_all()
    for domain in all_domains:
        for report_config in get_report_configs_for_domain(domain.name):
            yield report_config


@unit_testing_only
def delete_all_report_configs():
    from corehq.apps.userreports.models import ReportConfiguration
    delete_all_docs_by_doc_type(ReportConfiguration.get_db(), ('ReportConfiguration',))


def get_all_es_data_sources():
    from corehq.apps.userreports.data_source_providers import DynamicDataSourceProvider, StaticDataSourceProvider
    data_sources = DynamicDataSourceProvider().get_data_sources()
    data_sources.extend(StaticDataSourceProvider().get_data_sources())
    return [s for s in data_sources if s.backend_id in [UCR_ES_BACKEND, UCR_LABORATORY_BACKEND, UCR_ES_PRIMARY]]
