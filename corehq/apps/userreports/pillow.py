from __future__ import absolute_import
from collections import defaultdict
from datetime import datetime, timedelta
import hashlib

from alembic.autogenerate.api import compare_metadata
import six

from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed, MultiTopicCheckpointEventHandler
from corehq.apps.userreports.const import (
    KAFKA_TOPICS, UCR_ES_BACKEND, UCR_SQL_BACKEND, UCR_LABORATORY_BACKEND
)
from corehq.apps.userreports.data_source_providers import DynamicDataSourceProvider, StaticDataSourceProvider
from corehq.apps.userreports.exceptions import TableRebuildError, StaleRebuildError
from corehq.apps.userreports.sql import metadata
from corehq.apps.userreports.tasks import rebuild_indicators, save_document
from corehq.apps.userreports.util import get_indicator_adapter, get_backend_id
from corehq.sql_db.connections import connection_manager
from corehq.util.soft_assert import soft_assert
from fluff.signals import get_migration_context, get_tables_to_rebuild, reformat_alembic_diffs
from pillowtop.checkpoints.manager import PillowCheckpoint
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors import PillowProcessor
from pillowtop.utils import ensure_matched_revisions, ensure_document_exists
from pillow_retry.models import PillowError

REBUILD_CHECK_INTERVAL = 60 * 60  # in seconds


class ConfigurableReportTableManagerMixin(object):

    def __init__(self, data_source_provider, auto_repopulate_tables=False, *args, **kwargs):
        self.bootstrapped = False
        self.last_bootstrapped = datetime.utcnow()
        self.data_source_provider = data_source_provider
        self.auto_repopulate_tables = auto_repopulate_tables
        self.ucr_division = kwargs.pop('ucr_division', None)
        self.include_ucrs = kwargs.pop('include_ucrs', None)
        self.exclude_ucrs = kwargs.pop('exclude_ucrs', None)
        super(ConfigurableReportTableManagerMixin, self).__init__(*args, **kwargs)

    def get_all_configs(self):
        return self.data_source_provider.get_data_sources()

    def get_filtered_configs(self, configs=None):
        configs = configs or self.get_all_configs()

        if self.exclude_ucrs:
            configs = [config for config in configs if config.table_id not in self.exclude_ucrs]

        if self.include_ucrs:
            configs = [config for config in configs if config.table_id in self.include_ucrs]
        elif self.ucr_division:
            ucr_start = self.ucr_division[0]
            ucr_end = self.ucr_division[-1]
            filtered_configs = []
            for config in configs:
                table_hash = hashlib.md5(config.table_id).hexdigest()[0]
                if ucr_start <= table_hash <= ucr_end:
                    filtered_configs.append(configs)
            configs = filtered_configs

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
        self.table_adapters_by_domain = defaultdict(list)

        for config in configs:
            self.table_adapters_by_domain[config.domain].append(
                get_indicator_adapter(config, can_handle_laboratory=True)
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
        sql_supported_backends = [UCR_SQL_BACKEND, UCR_LABORATORY_BACKEND]
        es_supported_backends = [UCR_ES_BACKEND, UCR_LABORATORY_BACKEND]
        self._rebuild_sql_tables(self._tables_by_engine_id(sql_supported_backends))
        self._rebuild_es_tables(self._tables_by_engine_id(es_supported_backends))

    def _rebuild_sql_tables(self, adapters):
        # todo move this code to sql adapter rebuild_if_necessary
        tables_by_engine = defaultdict(dict)
        for adapter in adapters:
            sql_adapter = get_indicator_adapter(adapter.config)
            tables_by_engine[sql_adapter.engine_id][sql_adapter.get_table().name] = sql_adapter

        _assert = soft_assert(notify_admins=True)
        _notify_rebuild = lambda msg, obj: _assert(False, msg, obj)

        for engine_id, table_map in tables_by_engine.items():
            engine = connection_manager.get_engine(engine_id)
            with engine.begin() as connection:
                migration_context = get_migration_context(connection, list(table_map))
                raw_diffs = compare_metadata(migration_context, metadata)
                diffs = reformat_alembic_diffs(raw_diffs)

            tables_to_rebuild = get_tables_to_rebuild(diffs, list(table_map))
            for table_name in tables_to_rebuild:
                sql_adapter = table_map[table_name]
                if not sql_adapter.config.is_static:
                    try:
                        self.rebuild_table(sql_adapter)
                    except TableRebuildError as e:
                        _notify_rebuild(six.text_type(e), sql_adapter.config.to_json())
                else:
                    self.rebuild_table(sql_adapter)

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

    def process_change(self, pillow_instance, change):
        self.bootstrap_if_needed()
        if change.deleted:
            # we don't currently support hard-deletions at all.
            # we may want to change this at some later date but seem ok for now.
            # see https://github.com/dimagi/commcare-hq/pull/6944 for rationale
            return

        domain = change.metadata.domain
        if not domain:
            # if no domain we won't save to any UCR table
            return

        async_tables = []

        for table in self.table_adapters_by_domain[domain]:
            doc = change.get_document()
            ensure_document_exists(change)
            ensure_matched_revisions(change)
            if table.config.filter(doc):
                if table.run_asynchronous:
                    async_tables.append(table.config._id)
                else:
                    # best effort will swallow errors in the table
                    table.best_effort_save(doc)
            elif table.config.deleted_filter(doc):
                table.delete(doc)

        if async_tables:
            future_time = datetime.utcnow() + timedelta(days=1)
            error = PillowError.get_or_create(change, pillow_instance)
            error.date_next_attempt = future_time
            error.save()
            save_document.delay(async_tables, doc, pillow_instance.pillow_id)


class ConfigurableReportKafkaPillow(ConstructedPillow):
    # the only reason this is a class is to avoid exposing processors
    # for tests to be able to call bootstrap on it.
    # we could easily remove the class and push all the stuff in __init__ to
    # get_kafka_ucr_pillow below if we wanted.

    # don't retry errors until we figure out how to distinguish between
    # doc save errors and data source config errors
    retry_errors = False

    def __init__(self, processor, pillow_name, topics):
        change_feed = KafkaChangeFeed(topics, group_id=pillow_name)
        checkpoint = PillowCheckpoint(pillow_name)
        event_handler = MultiTopicCheckpointEventHandler(
            checkpoint=checkpoint, checkpoint_frequency=1000, change_feed=change_feed
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

    def bootstrap(self, configs=None):
        self._processor.bootstrap(configs)

    def rebuild_table(self, sql_adapter):
        self._processor.rebuild_table(sql_adapter)


# TODO(Emord) make other pillows support params dictionary
def get_kafka_ucr_pillow(pillow_id='kafka-ucr-main', ucr_division=None,
                         include_ucrs=None, exclude_ucrs=None, topics=None):
    topics = topics or KAFKA_TOPICS
    return ConfigurableReportKafkaPillow(
        processor=ConfigurableReportPillowProcessor(
            data_source_provider=DynamicDataSourceProvider(),
            auto_repopulate_tables=False,
            ucr_division=ucr_division,
            include_ucrs=include_ucrs,
            exclude_ucrs=exclude_ucrs,
        ),
        pillow_name=pillow_id,
        topics=topics
    )


def get_kafka_ucr_static_pillow(pillow_id='kafka-ucr-static', ucr_division=None,
                                include_ucrs=None, exclude_ucrs=None, topics=None):
    topics = topics or KAFKA_TOPICS
    return ConfigurableReportKafkaPillow(
        processor=ConfigurableReportPillowProcessor(
            data_source_provider=StaticDataSourceProvider(),
            auto_repopulate_tables=True,
            ucr_division=ucr_division,
            include_ucrs=include_ucrs,
            exclude_ucrs=exclude_ucrs,
        ),
        pillow_name=pillow_id,
        topics=topics
    )
