import hashlib
import signal
from abc import ABC, abstractmethod
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from django.conf import settings

from corehq.apps.change_feed.consumer.feed import (
    KafkaChangeFeed,
    KafkaCheckpointEventHandler,
)
from corehq.apps.change_feed.topics import LOCATION as LOCATION_TOPIC
from corehq.apps.domain.dbaccessors import get_domain_ids_by_names
from corehq.apps.domain_migration_flags.api import all_domains_with_migrations_in_progress
from corehq.apps.userreports.const import KAFKA_TOPICS
from corehq.apps.userreports.data_source_providers import (
    DynamicDataSourceProvider,
    StaticDataSourceProvider,
)
from corehq.apps.userreports.exceptions import (
    UserReportsWarning,
)
from corehq.apps.userreports.models import AsyncIndicator
from corehq.apps.userreports.pillow_utils import rebuild_sql_tables
from corehq.apps.userreports.specs import EvaluationContext
from corehq.apps.userreports.util import get_indicator_adapter
from corehq.pillows.base import is_couch_change_for_sql_domain
from corehq.util.metrics import metrics_counter, metrics_histogram_timer
from corehq.util.timer import TimingContext
from pillowtop.checkpoints.manager import KafkaPillowCheckpoint
from pillowtop.const import DEFAULT_PROCESSOR_CHUNK_SIZE
from pillowtop.exceptions import PillowConfigError
from pillowtop.logger import pillow_logging
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors import BulkPillowProcessor
from pillowtop.utils import ensure_document_exists, ensure_matched_revisions, bulk_fetch_changes_docs

REBUILD_CHECK_INTERVAL = 3 * 60 * 60  # in seconds
LONG_UCR_LOGGING_THRESHOLD = 0.5


class WarmShutdown(object):
    # modified from https://stackoverflow.com/a/50174144

    shutting_down = False

    def __enter__(self):
        self.current_handler = signal.signal(signal.SIGTERM, self.handler)

    def __exit__(self, exc_type, exc_value, traceback):
        if self.shutting_down and exc_type is None:
            exit(0)
        signal.signal(signal.SIGTERM, self.current_handler)

    def handler(self, signum, frame):
        self.shutting_down = True


def time_ucr_process_change(method):
    def timed(*args, **kw):
        ts = datetime.now()
        result = method(*args, **kw)
        te = datetime.now()
        seconds = (te - ts).total_seconds()
        if seconds > LONG_UCR_LOGGING_THRESHOLD:
            table = args[2]
            doc = args[3]
            log_message = "UCR data source {} on doc_id {} took {} seconds to process".format(
                table.config._id, doc['_id'], seconds
            )
            pillow_logging.warning(log_message)
        return result
    return timed


def _filter_by_hash(configs, ucr_division):
    ucr_start = ucr_division[0]
    ucr_end = ucr_division[-1]
    filtered_configs = []
    for config in configs:
        table_hash = hashlib.md5(config.table_id.encode('utf-8')).hexdigest()[0]
        if ucr_start <= table_hash <= ucr_end:
            filtered_configs.append(config)
    return filtered_configs


def _filter_domains_to_skip(configs):
    """Return a list of configs whose domain exists on this environment"""
    domain_names = list({config.domain for config in configs if config.is_static})
    existing_domains = list(get_domain_ids_by_names(domain_names))
    migrating_domains = all_domains_with_migrations_in_progress()
    return [
        config for config in configs
        if config.domain not in migrating_domains and (not config.is_static or config.domain in existing_domains)
    ]


def _filter_invalid_config(configs):
    """Return a list of configs that have been validated"""
    valid_configs = []
    for config in configs:
        try:
            config.validate()
            valid_configs.append(config)
        except Exception:
            pillow_logging.warning("Invalid config found during bootstrap: %s", config._id)
    return valid_configs


def _get_indicator_adapter_for_pillow(config):
    return get_indicator_adapter(config, raise_errors=True, load_source='change_feed')


class UcrTableManager(ABC):
    """Base class for table managers that encapsulates the bootstrap and refresh
    functionality."""
    def __init__(self, bootstrap_interval):
        self.bootstrapped = False
        self.last_bootstrapped = self.last_imported = datetime.utcnow()
        self.bootstrap_interval = bootstrap_interval

    def needs_bootstrap(self):
        """Returns True if the manager needs to be bootstrapped"""
        return (
            not self.bootstrapped
            or datetime.utcnow() - self.last_bootstrapped > timedelta(seconds=self.bootstrap_interval)
        )

    def bootstrap_if_needed(self):
        """Bootstrap the manager with data sources or else check for updated data sources"""
        if self.needs_bootstrap():
            self.bootstrap()
        else:
            self._update_modified_data_sources()

    def bootstrap(self, configs=None):
        """Initialize the manager with data sources and adapters"""
        self._do_bootstrap(configs=configs)
        self.bootstrapped = True
        self.last_bootstrapped = datetime.utcnow()

    @abstractmethod
    def _do_bootstrap(self, configs=None):
        """Override this method to actually perform the bootstrapping"""
        pass

    def _update_modified_data_sources(self):
        """Update the manager with any data sources that have been modified since the last call."""
        new_last_imported = datetime.utcnow()
        self._update_modified_since(self.last_imported)
        self.last_imported = new_last_imported

    @abstractmethod
    def _update_modified_since(self, timestamp):
        """Override this method to check for updated data sources and update the manager."""
        pass

    @property
    @abstractmethod
    def relevant_domains(self):
        """Return a list of domains that are relevant to the data sources in this manager."""
        pass

    @abstractmethod
    def get_adapters(self, domain):
        """Get the list of table adapters for the given domain."""
        pass

    @abstractmethod
    def get_all_adapters(self):
        """Get all table adapters managed by this manager."""
        pass

    @abstractmethod
    def remove_adapter(self, domain, adapter):
        """Remove an adapter from the list of managed adapters. This is called if there is an error
        writing to the adapter. The adapter will get re-added on next bootstrap."""
        pass

    def rebuild_tables_if_necessary(self):
        rebuild_sql_tables(self.get_all_adapters())


class ConfigurableReportTableManager(UcrTableManager):

    def __init__(self, data_source_providers, ucr_division=None,
                 include_ucrs=None, exclude_ucrs=None, bootstrap_interval=REBUILD_CHECK_INTERVAL,
                 run_migrations=True):
        """Initializes the processor for UCRs

        Keyword Arguments:
        ucr_division -- two hexadecimal digits that are used to determine a subset of UCR
                        datasources to process. The second digit should be higher than the
                        first
        include_ucrs -- list of ucr 'table_ids' to be included in this processor
        exclude_ucrs -- list of ucr 'table_ids' to be excluded in this processor
        bootstrap_interval -- time in seconds when the pillow checks for any data source changes
        run_migrations -- If True, rebuild tables if the data source changes.
                          Otherwise, do not attempt to change database
        """
        super().__init__(bootstrap_interval)
        self.data_source_providers = data_source_providers
        self.ucr_division = ucr_division
        self.include_ucrs = include_ucrs
        self.exclude_ucrs = exclude_ucrs
        self.run_migrations = run_migrations
        if self.include_ucrs and self.ucr_division:
            raise PillowConfigError("You can't have include_ucrs and ucr_division")

    def get_all_configs(self):
        return [
            source
            for provider in self.data_source_providers
            for source in provider.get_data_sources()
        ]

    def get_filtered_configs(self, configs=None):
        configs = configs or self.get_all_configs()

        if self.exclude_ucrs:
            configs = [config for config in configs if config.table_id not in self.exclude_ucrs]

        if self.include_ucrs:
            configs = [config for config in configs if config.table_id in self.include_ucrs]
        elif self.ucr_division:
            configs = _filter_by_hash(configs, self.ucr_division)

        configs = _filter_domains_to_skip(configs)
        configs = _filter_invalid_config(configs)

        return configs

    def _do_bootstrap(self, configs=None):
        configs = self.get_filtered_configs(configs)
        if not configs:
            pillow_logging.warning("UCR pillow has no configs to process")

        self.table_adapters_by_domain = defaultdict(list)

        for config in configs:
            self.table_adapters_by_domain[config.domain].append(
                _get_indicator_adapter_for_pillow(config)
            )

        if self.run_migrations:
            self.rebuild_tables_if_necessary()

    @property
    def relevant_domains(self):
        return set(self.table_adapters_by_domain)

    def get_adapters(self, domain):
        return list(self.table_adapters_by_domain.get(domain, []))

    def get_all_adapters(self):
        return [
            adapter
            for adapter_list in self.table_adapters_by_domain.values()
            for adapter in adapter_list
        ]

    def remove_adapter(self, domain, adapter):
        self.table_adapters_by_domain[domain].remove(adapter)

    def _update_modified_since(self, timestamp):
        """
        Find any data sources that have been modified since the last time this was bootstrapped
        and update the in-memory references.
        """
        new_data_sources = [
            source
            for provider in self.data_source_providers
            for source in provider.get_data_sources_modified_since(timestamp)
        ]
        self._add_data_sources_to_table_adapters(new_data_sources)

    def _add_data_sources_to_table_adapters(self, new_data_sources):
        for new_data_source in new_data_sources:
            pillow_logging.info(f'updating modified data source: {new_data_source.domain}: {new_data_source._id}')
            domain_adapters = self.table_adapters_by_domain[new_data_source.domain]
            # remove any previous adapters if they existed
            domain_adapters = [
                adapter for adapter in domain_adapters if adapter.config._id != new_data_source._id
            ]
            # add a new one
            domain_adapters.append(_get_indicator_adapter_for_pillow(new_data_source))
            # update dictionary
            self.table_adapters_by_domain[new_data_source.domain] = domain_adapters


class ConfigurableReportPillowProcessor(BulkPillowProcessor):
    """Generic processor for UCR.

    Reads from:
      - SQLLocation
      - Form data source
      - Case data source

    Writes to:
      - UCR database
    """

    def __init__(self, table_manager):
        self.table_manager = table_manager

    domain_timing_context = Counter()

    @time_ucr_process_change
    def _save_doc_to_table(self, domain, table, doc, eval_context):
        # best effort will swallow errors in the table
        try:
            table.best_effort_save(doc, eval_context)
        except UserReportsWarning:
            # remove it until the next bootstrap call
            self.table_manager.remove_adapter(domain, table)

    def process_changes_chunk(self, changes):
        """
        Update UCR tables in bulk by breaking up changes per domain per UCR table.
            If an exception is raised in bulk operations of a set of changes,
            those changes are returned to pillow for serial reprocessing.
        """
        self.bootstrap_if_needed()
        # break up changes by domain
        changes_by_domain = defaultdict(list)
        for change in changes:
            if is_couch_change_for_sql_domain(change):
                continue
            # skip if no domain or no UCR tables in the domain
            if change.metadata.domain and change.metadata.domain in self.table_manager.relevant_domains:
                changes_by_domain[change.metadata.domain].append(change)

        retry_changes = set()
        change_exceptions = []
        for domain, changes_chunk in changes_by_domain.items():
            with WarmShutdown():
                failed, exceptions = self._process_chunk_for_domain(domain, changes_chunk)
            retry_changes.update(failed)
            change_exceptions.extend(exceptions)

        return retry_changes, change_exceptions

    def _process_chunk_for_domain(self, domain, changes_chunk):
        adapters = self.table_manager.get_adapters(domain)
        changes_by_id = {change.id: change for change in changes_chunk}
        to_delete_by_adapter = defaultdict(list)
        rows_to_save_by_adapter = defaultdict(list)
        async_configs_by_doc_id = defaultdict(list)
        to_update = {change for change in changes_chunk if not change.deleted}
        with self._metrics_timer('extract'):
            retry_changes, docs = bulk_fetch_changes_docs(to_update, domain)
        change_exceptions = []

        with self._metrics_timer('single_batch_transform'):
            for doc in docs:
                change = changes_by_id[doc['_id']]
                doc_subtype = change.metadata.document_subtype
                eval_context = EvaluationContext(doc)
                with self._metrics_timer('single_doc_transform'):
                    for adapter in adapters:
                        with self._per_config_metrics_timer('transform', adapter.config._id):
                            if adapter.config.filter(doc, eval_context):
                                if adapter.run_asynchronous:
                                    async_configs_by_doc_id[doc['_id']].append(adapter.config._id)
                                else:
                                    try:
                                        rows_to_save_by_adapter[adapter].extend(adapter.get_all_values(doc, eval_context))
                                    except Exception as e:
                                        change_exceptions.append((change, e))
                                    eval_context.reset_iteration()
                            elif (not doc_subtype
                                    or doc_subtype in adapter.config.get_case_type_or_xmlns_filter()):
                                # Delete if the subtype is unknown or
                                # if the subtype matches our filters, but the full filter no longer applies
                                to_delete_by_adapter[adapter].append(doc)

        with self._metrics_timer('single_batch_delete'):
            # bulk delete by adapter
            to_delete = [{'_id': c.id} for c in changes_chunk if c.deleted]
            for adapter in adapters:
                delete_docs = to_delete_by_adapter[adapter] + to_delete
                if not delete_docs:
                    continue
                with self._per_config_metrics_timer('delete', adapter.config._id):
                    try:
                        adapter.bulk_delete(delete_docs)
                    except Exception:
                        delete_ids = [doc['_id'] for doc in delete_docs]
                        retry_changes.update([c for c in changes_chunk if c.id in delete_ids])

        with self._metrics_timer('single_batch_load'):
            # bulk update by adapter
            for adapter, rows in rows_to_save_by_adapter.items():
                with self._per_config_metrics_timer('load', adapter.config._id):
                    try:
                        adapter.save_rows(rows)
                    except Exception:
                        retry_changes.update(to_update)

        if async_configs_by_doc_id:
            with self._metrics_timer('async_config_load'):
                doc_type_by_id = {
                    _id: changes_by_id[_id].metadata.document_type
                    for _id in async_configs_by_doc_id.keys()
                }
                AsyncIndicator.bulk_update_records(async_configs_by_doc_id, domain, doc_type_by_id)

        return retry_changes, change_exceptions

    def _metrics_timer(self, step, config_id=None):
        tags = {
            'action': step,
            'index': 'ucr',
        }
        if config_id and settings.ENTERPRISE_MODE:
            tags['config_id'] = config_id
        return metrics_histogram_timer(
            'commcare.change_feed.processor.timing',
            timing_buckets=(.03, .1, .3, 1, 3, 10), tags=tags
        )

    def _per_config_metrics_timer(self, step, config_id):
        tags = {
            'action': step,
        }
        if settings.ENTERPRISE_MODE:
            tags['config_id'] = config_id
        return metrics_histogram_timer(
            'commcare.change_feed.urc.timing',
            timing_buckets=(.03, .1, .3, 1, 3, 10), tags=tags
        )

    def process_change(self, change):
        self.bootstrap_if_needed()

        domain = change.metadata.domain
        if not domain or domain not in self.table_manager.relevant_domains:
            # if no domain we won't save to any UCR table
            return

        if change.deleted:
            adapters = self.table_manager.get_adapters(domain)
            for table in adapters:
                table.delete({'_id': change.metadata.document_id})

        async_tables = []
        doc = change.get_document()
        ensure_document_exists(change)
        ensure_matched_revisions(change, doc)

        if doc is None:
            return

        with TimingContext() as timer:
            eval_context = EvaluationContext(doc)
            # make copy to avoid modifying list during iteration
            adapters = self.table_manager.get_adapters(domain)
            doc_subtype = change.metadata.document_subtype
            for table in adapters:
                if table.config.filter(doc, eval_context):
                    if table.run_asynchronous:
                        async_tables.append(table.config._id)
                    else:
                        self._save_doc_to_table(domain, table, doc, eval_context)
                        eval_context.reset_iteration()
                elif (doc_subtype is None
                        or doc_subtype in table.config.get_case_type_or_xmlns_filter()):
                    table.delete(doc)

            if async_tables:
                AsyncIndicator.update_from_kafka_change(change, async_tables)

        self.domain_timing_context.update(**{
            domain: timer.duration
        })

    def checkpoint_updated(self):
        total_duration = sum(self.domain_timing_context.values())
        duration_seen = 0
        top_half_domains = {}
        for domain, duration in self.domain_timing_context.most_common():
            top_half_domains[domain] = duration
            duration_seen += duration
            if duration_seen >= total_duration // 2:
                break

        for domain, duration in top_half_domains.items():
            metrics_counter('commcare.change_feed.ucr_slow_log', duration, tags={
                'domain': domain
            })
        self.domain_timing_context.clear()

    def bootstrap_if_needed(self):
        self.table_manager.bootstrap_if_needed()



class ConfigurableReportKafkaPillow(ConstructedPillow):
    # todo; To remove after full rollout of https://github.com/dimagi/commcare-hq/pull/21329/

    def __init__(self, processor, pillow_name, topics, num_processes, process_num, retry_errors=False,
            is_dedicated_migration_process=False, processor_chunk_size=0):
        change_feed = KafkaChangeFeed(
            topics, client_id=pillow_name, num_processes=num_processes, process_num=process_num
        )
        checkpoint = KafkaPillowCheckpoint(pillow_name, topics)
        event_handler = KafkaCheckpointEventHandler(
            checkpoint=checkpoint, checkpoint_frequency=1000, change_feed=change_feed,
            checkpoint_callback=processor
        )
        super(ConfigurableReportKafkaPillow, self).__init__(
            name=pillow_name,
            change_feed=change_feed,
            processor=processor,
            checkpoint=checkpoint,
            change_processed_event_handler=event_handler,
            processor_chunk_size=processor_chunk_size
        )
        # set by the superclass constructor
        assert self.processors is not None
        assert len(self.processors) == 1
        self._processor = self.processors[0]
        assert self._processor.table_manager.bootstrapped is not None

        # retry errors defaults to False because there is not a solution to
        # distinguish between doc save errors and data source config errors
        self.retry_errors = retry_errors


def get_kafka_ucr_pillow(pillow_id='kafka-ucr-main', ucr_division=None,
                         include_ucrs=None, exclude_ucrs=None, topics=None,
                         num_processes=1, process_num=0, dedicated_migration_process=False,
                         processor_chunk_size=DEFAULT_PROCESSOR_CHUNK_SIZE, **kwargs):
    """UCR pillow that reads from all Kafka topics and writes data into the UCR database tables.

        Processors:
          - :py:class:`corehq.apps.userreports.pillow.ConfigurableReportPillowProcessor`
    """
    # todo; To remove after full rollout of https://github.com/dimagi/commcare-hq/pull/21329/
    topics = topics or KAFKA_TOPICS
    topics = [t for t in topics]
    table_manager = ConfigurableReportTableManager(
        data_source_providers=[DynamicDataSourceProvider()],
        ucr_division=ucr_division,
        include_ucrs=include_ucrs,
        exclude_ucrs=exclude_ucrs,
        run_migrations=(process_num == 0)  # only first process runs migrations
    )
    return ConfigurableReportKafkaPillow(
        processor=ConfigurableReportPillowProcessor(table_manager),
        pillow_name=pillow_id,
        topics=topics,
        num_processes=num_processes,
        process_num=process_num,
        is_dedicated_migration_process=dedicated_migration_process and (process_num == 0),
        processor_chunk_size=processor_chunk_size,
    )


def get_kafka_ucr_static_pillow(pillow_id='kafka-ucr-static', ucr_division=None,
                                include_ucrs=None, exclude_ucrs=None, topics=None,
                                num_processes=1, process_num=0, dedicated_migration_process=False,
                                processor_chunk_size=DEFAULT_PROCESSOR_CHUNK_SIZE, **kwargs):
    """UCR pillow that reads from all Kafka topics and writes data into the UCR database tables.

    Only processes `static` UCR datasources (configuration lives in the codebase instead of the database).

        Processors:
          - :py:class:`corehq.apps.userreports.pillow.ConfigurableReportPillowProcessor`
    """
    # todo; To remove after full rollout of https://github.com/dimagi/commcare-hq/pull/21329/
    topics = topics or KAFKA_TOPICS
    topics = [t for t in topics]
    table_manager = ConfigurableReportTableManager(
        data_source_providers=[StaticDataSourceProvider()],
        ucr_division=ucr_division,
        include_ucrs=include_ucrs,
        exclude_ucrs=exclude_ucrs,
        bootstrap_interval=7 * 24 * 60 * 60,  # 1 week
        run_migrations=(process_num == 0)  # only first process runs migrations
    )
    return ConfigurableReportKafkaPillow(
        processor=ConfigurableReportPillowProcessor(table_manager),
        pillow_name=pillow_id,
        topics=topics,
        num_processes=num_processes,
        process_num=process_num,
        retry_errors=True,
        is_dedicated_migration_process=dedicated_migration_process and (process_num == 0),
        processor_chunk_size=processor_chunk_size,
    )


def get_location_pillow(pillow_id='location-ucr-pillow', include_ucrs=None,
                        num_processes=1, process_num=0, ucr_configs=None, **kwargs):
    """Processes updates to locations for UCR

    Note this is only applicable if a domain on the environment has `LOCATIONS_IN_UCR` flag enabled.

    Processors:
      - :py:func:`corehq.apps.userreports.pillow.ConfigurableReportPillowProcessor`
    """
    change_feed = KafkaChangeFeed(
        [LOCATION_TOPIC], client_id=pillow_id, num_processes=num_processes, process_num=process_num
    )
    table_manager = ConfigurableReportTableManager(
        data_source_providers=[
            DynamicDataSourceProvider('Location'),
            StaticDataSourceProvider('Location')
        ],
        include_ucrs=include_ucrs
    )
    ucr_processor = ConfigurableReportPillowProcessor(table_manager)
    if ucr_configs:
        table_manager.bootstrap(ucr_configs)
    checkpoint = KafkaPillowCheckpoint(pillow_id, [LOCATION_TOPIC])
    event_handler = KafkaCheckpointEventHandler(
        checkpoint=checkpoint, checkpoint_frequency=1000, change_feed=change_feed,
        checkpoint_callback=ucr_processor
    )
    return ConstructedPillow(
        name=pillow_id,
        change_feed=change_feed,
        checkpoint=checkpoint,
        change_processed_event_handler=event_handler,
        processor=[ucr_processor]
    )
