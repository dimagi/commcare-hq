import logging
from collections import defaultdict
from textwrap import dedent

from sqlalchemy.exc import ProgrammingError

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


def get_deletable_ucrs(orphaned_tables_by_id, force_delete=False, domain=None):
    """
    Ensures tables are UCRs via inserted_at column
    :param orphaned_tables_by_id: {<engine_id>: [<tablename>, ...]}
    :param force_delete: if True, orphaned tables associated with active domains are marked as deletable
    :param domain: optional, but if specified will only gather ucrs from the specified domain
    :return:
    """
    ucrs_to_delete = defaultdict(list)
    active_domains_with_orphaned_ucrs = set()
    for engine_id, tablenames in orphaned_tables_by_id.items():
        engine = connection_manager.get_engine(engine_id)
        if not tablenames:
            continue

        for tablename in tablenames:
            domain_for_table = get_domain_for_ucr_table_name(tablename)

            if domain and domain != domain_for_table:
                continue

            if not force_delete and not Domain.is_domain_deleted(domain_for_table):
                active_domains_with_orphaned_ucrs.add(domain_for_table)
                continue

            with engine.begin() as connection:
                try:
                    result = connection.execute(f'SELECT COUNT(*), MAX(inserted_at) FROM "{tablename}"')
                except ProgrammingError:
                    print(f"\t{tablename}: no inserted_at column, probably not UCR")
                except Exception as e:
                    print(f"\tAn error was encountered when attempting to read from {tablename}: {e}")
                else:
                    row_count, idle_since = result.fetchone()
                    ucrs_to_delete[engine_id].append({'tablename': tablename, 'row_count': row_count})

    if not force_delete and active_domains_with_orphaned_ucrs:
        formatted_domains = '\n'.join(sorted(active_domains_with_orphaned_ucrs))
        error_message = dedent("""
            {} active domain(s) have orphaned ucrs.
            The domains are:
            {}
            """).format(len(active_domains_with_orphaned_ucrs),
                        formatted_domains)
        raise AssertionError(error_message)

    return ucrs_to_delete


def get_orphaned_tables_by_engine_id(engine_id=None):
    """
    :param engine_id: optional parameter to only search within a specific database
    :return: {<engine_id>: [<tablename>, ...]}
    """
    data_sources = get_all_data_sources()
    tables_by_engine_id = _get_tables_for_data_sources(data_sources, engine_id)
    return _get_tables_without_data_sources(tables_by_engine_id)


def _get_tables_for_data_sources(data_sources, engine_id=None):
    """
    :param data_sources:
    :param engine_id: optional parameter to limit results to one db engine
    :return: a dictionary in the form of {<engine_id>: [<tables>], ...}
    """
    tables_by_engine_id = defaultdict(set)
    for data_source in data_sources:
        if engine_id and data_source.engine_id != engine_id:
            continue

        table_name = get_table_name(data_source.domain, data_source.table_id)
        tables_by_engine_id[data_source.engine_id].add(table_name)

    return tables_by_engine_id


def _get_tables_without_data_sources(tables_by_engine_id):
    """
    :param tables_by_engine_id:
    :return: a dictionary in the form of {<engine_id>: [<tables], ...}
    """
    tables_without_data_sources = defaultdict(list)
    for engine_id, expected_tables in tables_by_engine_id.items():
        try:
            engine = connection_manager.get_engine(engine_id)
        except KeyError:
            print(f"Engine id {engine_id} does not exist anymore. Skipping.")
            continue
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
            tables_in_db = {r[0] for r in results}
        tables_without_data_sources[engine_id] = tables_in_db - expected_tables
    return tables_without_data_sources


def drop_ucr_tables(ucr_tables_by_engine_id):
    """
    :param ucr_tables_by_engine_id: {'<engine_id>': [<tablename>, ...]}
    """
    for engine_id, tablenames in ucr_tables_by_engine_id.items():
        engine = connection_manager.get_engine(engine_id)
        if not tablenames:
            continue

        for tablename in tablenames:
            with engine.begin() as connection:
                connection.execute(f'DROP TABLE "{tablename}"')
                logger.info(f'Deleted {tablename} from database {engine_id}')
