from __future__ import absolute_import

import hashlib
from collections import defaultdict, Counter
from datetime import datetime, timedelta

import six
from alembic.autogenerate.api import compare_metadata
from kafka.util import kafka_bytestring

from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed, KafkaCheckpointEventHandler
from corehq.apps.userreports.const import (
    KAFKA_TOPICS, UCR_ES_BACKEND, UCR_SQL_BACKEND, UCR_LABORATORY_BACKEND, UCR_ES_PRIMARY
)
from corehq.apps.userreports.data_source_providers import DynamicDataSourceProvider, StaticDataSourceProvider
from corehq.apps.userreports.exceptions import (
    BadSpecError, TableRebuildError, StaleRebuildError, UserReportsWarning
)
from corehq.apps.userreports.models import AsyncIndicator
from corehq.apps.userreports.specs import EvaluationContext
from corehq.apps.userreports.sql import metadata
from corehq.apps.userreports.tasks import rebuild_indicators
from corehq.apps.userreports.util import get_indicator_adapter, get_backend_id
from corehq.sql_db.connections import connection_manager
from corehq.util.datadog.gauges import datadog_histogram
from corehq.util.soft_assert import soft_assert
from corehq.util.timer import TimingContext
from fluff.signals import (
    migrate_tables,
    get_migration_context,
    get_tables_to_migrate,
    get_tables_to_rebuild,
    reformat_alembic_diffs
)
from pillowtop.checkpoints.manager import KafkaPillowCheckpoint
from pillowtop.logger import pillow_logging
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors import PillowProcessor
from pillowtop.utils import ensure_matched_revisions, ensure_document_exists

REBUILD_CHECK_INTERVAL = 60 * 60  # in seconds
LONG_UCR_LOGGING_THRESHOLD = 0.5


class PillowConfigError(Exception):
    pass


def time_ucr_process_change(method):
    def timed(*args, **kw):
        ts = datetime.now()
        result = method(*args, **kw)
        te = datetime.now()
        seconds = (te - ts).total_seconds()
        if seconds > LONG_UCR_LOGGING_THRESHOLD:
            table = args[2]
            doc = args[3]
            log_message = u"UCR data source {} on doc_id {} took {} seconds to process".format(
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
        table_hash = hashlib.md5(config.table_id).hexdigest()[0]
        if ucr_start <= table_hash <= ucr_end:
            filtered_configs.append(config)
    return filtered_configs


class ConfigurableReportTableManagerMixin(object):

    def __init__(self, data_source_provider, auto_repopulate_tables=False, ucr_division=None,
                 include_ucrs=None, exclude_ucrs=None):
        """Initializes the processor for UCRs

        Keyword Arguments:
        ucr_division -- two hexadecimal digits that are used to determine a subset of UCR
                        datasources to process. The second digit should be higher than the
                        first
        include_ucrs -- list of ucr 'table_ids' to be included in this processor
        exclude_ucrs -- list of ucr 'table_ids' to be excluded in this processor
        """
        self.bootstrapped = False
        self.last_bootstrapped = datetime.utcnow()
        self.data_source_provider = data_source_provider
        self.auto_repopulate_tables = auto_repopulate_tables
        self.ucr_division = ucr_division
        self.include_ucrs = include_ucrs
        self.exclude_ucrs = exclude_ucrs
        if self.include_ucrs and self.ucr_division:
            raise PillowConfigError("You can't have include_ucrs and ucr_division")

    def get_all_configs(self):
        return self.data_source_provider.get_data_sources()

    def get_filtered_configs(self, configs=None):
        configs = configs or self.get_all_configs()

        if self.exclude_ucrs:
            configs = [config for config in configs if config.table_id not in self.exclude_ucrs]

        if self.include_ucrs:
            configs = [config for config in configs if config.table_id in self.include_ucrs]
        elif self.ucr_division:
            configs = _filter_by_hash(configs, self.ucr_division)

        return configs

    def needs_bootstrap(self):
        return (
            not self.bootstrapped
            or datetime.utcnow() - self.last_bootstrapped > timedelta(seconds=REBUILD_CHECK_INTERVAL)
        )

    def bootstrap_if_needed(self):
        if self.needs_bootstrap():
            self.bootstrap()

    def bootstrap(self, configs=None):
        configs = self.get_filtered_configs(configs)
        if not configs:
            pillow_logging.warning("UCR pillow has no configs to process")

        self.table_adapters_by_domain = defaultdict(list)

        for config in configs:
            self.table_adapters_by_domain[config.domain].append(
                get_indicator_adapter(config, can_handle_laboratory=True, raise_errors=True)
            )

        self.rebuild_tables_if_necessary()
        self.bootstrapped = True
        self.last_bootstrapped = datetime.utcnow()

    def _tables_by_engine_id(self, engine_ids):
        return [
            adapter
            for adapter_list in self.table_adapters_by_domain.values()
            for adapter in adapter_list
            if get_backend_id(adapter.config, can_handle_laboratory=True) in engine_ids
        ]

    def rebuild_tables_if_necessary(self):
        sql_supported_backends = [UCR_SQL_BACKEND, UCR_LABORATORY_BACKEND, UCR_ES_PRIMARY]
        es_supported_backends = [UCR_ES_BACKEND, UCR_LABORATORY_BACKEND, UCR_ES_PRIMARY]
        self._rebuild_sql_tables(self._tables_by_engine_id(sql_supported_backends))
        self._rebuild_es_tables(self._tables_by_engine_id(es_supported_backends))

    def _rebuild_sql_tables(self, adapters):
        tables_by_engine = defaultdict(dict)
        for adapter in adapters:
            sql_adapter = get_indicator_adapter(adapter.config)
            try:
                tables_by_engine[sql_adapter.engine_id][sql_adapter.get_table().name] = sql_adapter
            except BadSpecError:
                _soft_assert = soft_assert(to='{}@{}'.format('jemord', 'dimagi.com'))
                _soft_assert(False, "Broken data source {}".format(adapter.config.get_id))

        _assert = soft_assert(notify_admins=True)
        _notify_rebuild = lambda msg, obj: _assert(False, msg, obj)

        for engine_id, table_map in tables_by_engine.items():
            engine = connection_manager.get_engine(engine_id)
            table_names = list(table_map)
            with engine.begin() as connection:
                migration_context = get_migration_context(connection, table_names)
                raw_diffs = compare_metadata(migration_context, metadata)
                diffs = reformat_alembic_diffs(raw_diffs)

            tables_to_rebuild = get_tables_to_rebuild(diffs, table_names)
            for table_name in tables_to_rebuild:
                sql_adapter = table_map[table_name]
                if not sql_adapter.config.is_static:
                    try:
                        self.rebuild_table(sql_adapter)
                    except TableRebuildError as e:
                        _notify_rebuild(six.text_type(e), sql_adapter.config.to_json())
                else:
                    self.rebuild_table(sql_adapter)

            tables_to_migrate = get_tables_to_migrate(diffs, table_names)
            tables_to_migrate -= tables_to_rebuild
            migrate_tables(engine, raw_diffs, tables_to_migrate)

    def _rebuild_es_tables(self, adapters):
        # note unlike sql rebuilds this doesn't rebuild the indicators
        for adapter in adapters:
            adapter.rebuild_table_if_necessary()

    def rebuild_table(self, adapter):
        config = adapter.config
        if not config.is_static:
            latest_rev = config.get_db().get_rev(config._id)
            if config._rev != latest_rev:
                raise StaleRebuildError('Tried to rebuild a stale table ({})! Ignoring...'.format(config))
        adapter.rebuild_table()
        if self.auto_repopulate_tables:
            rebuild_indicators.delay(adapter.config.get_id)


class ConfigurableReportPillowProcessor(ConfigurableReportTableManagerMixin, PillowProcessor):

    domain_timing_context = Counter()

    @time_ucr_process_change
    def _save_doc_to_table(self, domain, table, doc, eval_context):
        # best effort will swallow errors in the table
        try:
            table.best_effort_save(doc, eval_context)
        except UserReportsWarning:
            # remove it until the next bootstrap call
            self.table_adapters_by_domain[domain].remove(table)

    def process_change(self, pillow_instance, change):
        self.bootstrap_if_needed()

        domain = change.metadata.domain
        if not domain or domain not in self.table_adapters_by_domain:
            # if no domain we won't save to any UCR table
            return

        if change.deleted:
            adapters = list(self.table_adapters_by_domain[domain])
            for table in adapters:
                table.delete({'_id': change.metadata.document_id})

        async_tables = []
        doc = change.get_document()
        ensure_document_exists(change)
        ensure_matched_revisions(change)

        if doc is None:
            return

        with TimingContext() as timer:
            eval_context = EvaluationContext(doc)
            # make copy to avoid modifying list during iteration
            adapters = list(self.table_adapters_by_domain[domain])
            for table in adapters:
                if table.config.filter(doc):
                    if table.run_asynchronous:
                        async_tables.append(table.config._id)
                    else:
                        self._save_doc_to_table(domain, table, doc, eval_context)
                        eval_context.reset_iteration()
                elif table.config.deleted_filter(doc) or table.doc_exists(doc):
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
            if duration_seen >= total_duration / 2:
                break

        for domain, duration in top_half_domains.items():
            datadog_histogram('commcare.change_feed.ucr_slow_log', duration, tags=[
                'domain:{}'.format(domain)
            ])
        self.domain_timing_context.clear()


class ConfigurableReportKafkaPillow(ConstructedPillow):
    # the only reason this is a class is to avoid exposing processors
    # for tests to be able to call bootstrap on it.
    # we could easily remove the class and push all the stuff in __init__ to
    # get_kafka_ucr_pillow below if we wanted.

    def __init__(self, processor, pillow_name, topics, num_processes, process_num, retry_errors=False):
        change_feed = KafkaChangeFeed(
            topics, group_id=pillow_name, num_processes=num_processes, process_num=process_num
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
            change_processed_event_handler=event_handler
        )
        # set by the superclass constructor
        assert self.processors is not None
        assert len(self.processors) == 1
        self._processor = self.processors[0]
        assert self._processor.bootstrapped is not None

        # retry errors defaults to False because there is not a solution to
        # distinguish between doc save errors and data source config errors
        self.retry_errors = retry_errors

    def bootstrap(self, configs=None):
        self._processor.bootstrap(configs)

    def rebuild_table(self, sql_adapter):
        self._processor.rebuild_table(sql_adapter)


def get_kafka_ucr_pillow(pillow_id='kafka-ucr-main', ucr_division=None,
                         include_ucrs=None, exclude_ucrs=None, topics=None,
                         num_processes=1, process_num=0, **kwargs):
    topics = topics or KAFKA_TOPICS
    topics = [kafka_bytestring(t) for t in topics]
    return ConfigurableReportKafkaPillow(
        processor=ConfigurableReportPillowProcessor(
            data_source_provider=DynamicDataSourceProvider(),
            auto_repopulate_tables=False,
            ucr_division=ucr_division,
            include_ucrs=include_ucrs,
            exclude_ucrs=exclude_ucrs,
        ),
        pillow_name=pillow_id,
        topics=topics,
        num_processes=num_processes,
        process_num=process_num,
    )


def get_kafka_ucr_static_pillow(pillow_id='kafka-ucr-static', ucr_division=None,
                                include_ucrs=None, exclude_ucrs=None, topics=None,
                                num_processes=1, process_num=0, **kwargs):
    topics = topics or KAFKA_TOPICS
    topics = [kafka_bytestring(t) for t in topics]
    return ConfigurableReportKafkaPillow(
        processor=ConfigurableReportPillowProcessor(
            data_source_provider=StaticDataSourceProvider(),
            auto_repopulate_tables=True,
            ucr_division=ucr_division,
            include_ucrs=include_ucrs,
            exclude_ucrs=exclude_ucrs,
        ),
        pillow_name=pillow_id,
        topics=topics,
        num_processes=num_processes,
        process_num=process_num,
        retry_errors=True
    )
