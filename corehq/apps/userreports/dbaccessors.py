import logging

from sqlalchemy.exc import ProgrammingError

from corehq.apps.cleanup.utils import DeletedDomains
from corehq.apps.domain.dbaccessors import get_docs_in_domain_by_class
from corehq.apps.domain.models import Domain
from corehq.apps.userreports.util import (
    LEGACY_UCR_TABLE_PREFIX,
    UCR_TABLE_PREFIX,
    get_domain_for_ucr_table_name,
    get_indicator_adapter,
    get_table_name,
)
from corehq.dbaccessors.couchapps.all_docs import delete_all_docs_by_doc_type
from corehq.sql_db.connections import connection_manager
from corehq.util.test_utils import unit_testing_only

logger = logging.getLogger(__name__)


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


def get_number_of_registry_report_configs_by_data_source(domain, data_source_id):
    """
    Return the number of data registry report configurations that use the given data source.
    """
    from corehq.apps.userreports.models import RegistryReportConfiguration
    result = RegistryReportConfiguration.view(
        'registry_report_configs/view',
        reduce=True,
        key=[domain, data_source_id]
    ).one()
    return result['value'] if result else 0


def get_registry_report_configs_for_domain(domain):
    from corehq.apps.userreports.models import RegistryReportConfiguration
    return sorted(
        get_docs_in_domain_by_class(domain, RegistryReportConfiguration),
        key=lambda report: report.title or '',
    )


def get_report_and_registry_report_configs_for_domain(domain):
    from corehq.apps.userreports.models import (
        ReportConfiguration,
        RegistryReportConfiguration,
    )
    configs = get_docs_in_domain_by_class(domain, ReportConfiguration)
    configs += get_docs_in_domain_by_class(domain, RegistryReportConfiguration)
    return sorted(
        configs,
        key=lambda report: report.title or '',
    )


def get_datasources_for_domain(domain, referenced_doc_type=None, include_static=False, include_aggregate=False):
    from corehq.apps.userreports.models import (
        DataSourceConfiguration,
        RegistryDataSourceConfiguration,
        StaticDataSourceConfiguration,
    )
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
    datasources.extend(sorted(
        RegistryDataSourceConfiguration.by_domain(domain), key=lambda config: config.display_name or '')
    )

    if include_static:
        static_ds = StaticDataSourceConfiguration.by_domain(domain)
        if referenced_doc_type:
            static_ds = [ds for ds in static_ds if ds.referenced_doc_type == referenced_doc_type]
        datasources.extend(sorted(static_ds, key=lambda config: config.display_name))

    if include_aggregate:
        from corehq.apps.aggregate_ucrs.models import AggregateTableDefinition
        datasources.extend(AggregateTableDefinition.objects.filter(domain=domain).all())
    return datasources


def get_all_data_sources():
    from corehq.apps.userreports.models import (
        DataSourceConfiguration,
        StaticDataSourceConfiguration,
    )
    data_sources = list(DataSourceConfiguration.all())
    data_sources.extend(list(StaticDataSourceConfiguration.all()))
    return data_sources


def get_registry_data_sources_by_domain(domain):
    from corehq.apps.userreports.models import RegistryDataSourceConfiguration
    return sorted(
        RegistryDataSourceConfiguration.view(
            'registry_data_sources/view',
            startkey=[domain],
            endkey=[domain, {}],
            reduce=False,
            include_docs=True,
        ),
        key=lambda config: config.display_name or ''
    )


def get_all_registry_data_source_ids(is_active=None, globally_accessible=None):
    from corehq.apps.userreports.models import RegistryDataSourceConfiguration
    rows = RegistryDataSourceConfiguration.view(
        'registry_data_sources/view',
        reduce=False,
        include_docs=False,
    )
    return [
        row["id"] for row in rows
        if (is_active is None or row["value"]["is_deactivated"] != is_active)
        and (globally_accessible is None or row["value"]["globally_accessible"] == globally_accessible)
    ]


def get_registry_data_sources_modified_since(timestamp):
    from corehq.apps.userreports.models import RegistryDataSourceConfiguration
    return RegistryDataSourceConfiguration.view(
        'registry_data_sources_by_last_modified/view',
        startkey=[timestamp.isoformat()],
        endkey=[{}],
        reduce=False,
        include_docs=True
    ).all()


@unit_testing_only
def get_all_report_configs():
    all_domains = Domain.get_all()
    for domain_obj in all_domains:
        for report_config in get_report_and_registry_report_configs_for_domain(domain_obj.name):
            yield report_config


@unit_testing_only
def delete_all_report_configs():
    from corehq.apps.userreports.models import ReportConfiguration
    delete_all_docs_by_doc_type(ReportConfiguration.get_db(), ('ReportConfiguration',))


def delete_all_ucr_tables_for_domain(domain):
    """
    For a given domain, delete all the known UCR data source tables

    This only deletes "known" data sources for the domain.
    To identify "orphaned" tables, see the manage_orphaned_ucrs management command.
    """
    for config in get_datasources_for_domain(domain):
        adapter = get_indicator_adapter(config)
        adapter.drop_table()


def get_orphaned_ucrs(engine_id, domain=None, ignore_active_domains=True):
    """
    :param engine_id: id of the database/engine to search in
    :param domain: (optional) domain name to limit search to
    :param ignore_active_domains: if True, only searches within deleted domains
    :return: list of tablenames
    """
    deleted_domains_cache = DeletedDomains()
    if domain and not deleted_domains_cache.is_domain_deleted(domain):
        assert not ignore_active_domains,\
            f"{domain} is active but ignore_active_domains is True"

    ucrs_with_datasources = _get_ucrs_with_datasources(engine_id,
                                                       domain,
                                                       ignore_active_domains,
                                                       deleted_domains_cache)
    all_ucrs = _get_existing_ucrs(engine_id,
                                  domain,
                                  ignore_active_domains,
                                  deleted_domains_cache)
    suspected_orphaned_ucrs = set(all_ucrs) - set(ucrs_with_datasources)
    return _get_confirmed_orphaned_ucrs(engine_id, suspected_orphaned_ucrs)


def _get_ucrs_with_datasources(engine_id, domain, ignore_active_domains,
                               deleted_domains_cache):
    ucrs_with_datasources = []
    if domain:
        datasources = get_datasources_for_domain(domain)
    else:
        datasources = get_all_data_sources()

    for datasource in datasources:
        if datasource.engine_id != engine_id:
            continue

        if ignore_active_domains and not \
                deleted_domains_cache.is_domain_deleted(datasource.domain):
            continue

        ucr = get_table_name(datasource.domain, datasource.table_id)
        ucrs_with_datasources.append(ucr)

    return ucrs_with_datasources


def _get_existing_ucrs(engine_id, domain, ignore_active_domains,
                       deleted_domains_cache):
    try:
        engine = connection_manager.get_engine(engine_id)
    except KeyError:
        raise ValueError(f"Engine id {engine_id} does not exist.")

    with engine.begin() as connection:
        # Using string formatting rather than execute with %s syntax
        # is acceptable here because the strings we're inserting are static
        # and only templated for DRYness
        results = connection.execute(f"""
        SELECT table_name
          FROM information_schema.tables
        WHERE table_schema='public'
          AND table_type='BASE TABLE'
          AND (
            table_name LIKE '{UCR_TABLE_PREFIX}%%'
            OR
            table_name LIKE '{LEGACY_UCR_TABLE_PREFIX}%%'
        );
        """).fetchall()
        all_existing_ucrs = [r[0] for r in results]

    if domain:
        all_existing_ucrs = [ucr for ucr in all_existing_ucrs if
                             get_domain_for_ucr_table_name(ucr) == domain]
    elif ignore_active_domains:
        # can use elif because this is redundant after a domain filter
        all_existing_ucrs = [ucr for ucr in all_existing_ucrs if
                             deleted_domains_cache.is_domain_deleted(
                                 get_domain_for_ucr_table_name(ucr))]

    return all_existing_ucrs


def _get_confirmed_orphaned_ucrs(engine_id, suspected_orphaned_ucrs):
    if not suspected_orphaned_ucrs:
        return []

    engine = connection_manager.get_engine(engine_id)
    confirmed_orphaned_ucrs = []
    for suspected_orphaned_ucr in suspected_orphaned_ucrs:
        with engine.begin() as connection:
            try:
                connection.execute(
                    f'SELECT COUNT(*), MAX(inserted_at) FROM "{suspected_orphaned_ucr}"')
            except ProgrammingError:
                print(f"\tEncountered ProgrammingError for {suspected_orphaned_ucr}\n"
                      f"\tCould be due to no inserted_at column which would mean this is not a UCR")
            except Exception as e:
                print(
                    f"\tAn error was encountered when attempting to read from "
                    f"{suspected_orphaned_ucr}: {e}")
            else:
                confirmed_orphaned_ucrs.append(suspected_orphaned_ucr)

    return confirmed_orphaned_ucrs


def drop_orphaned_ucrs(engine_id, ucrs):
    """
    WARNING: this method is intended for use with orphaned UCRs only
    If passing in a UCR with an existing datasource, the datasource will not be
    deleted along with the UCR table
    :param engine_id: id of engine/database to connect to
    :param ucrs: list of ucr tablenames to delete
    """
    engine = connection_manager.get_engine(engine_id)
    for ucr in ucrs:
        with engine.begin() as connection:
            connection.execute(f'DROP TABLE "{ucr}"')
            logger.info(f'Deleted {ucr} from database {engine_id}')
