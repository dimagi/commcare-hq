from __future__ import absolute_import
from collections import defaultdict
from alembic.autogenerate.api import compare_metadata
from datetime import datetime, timedelta
from corehq.apps.change_feed import topics
from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed, MultiTopicCheckpointEventHandler
from corehq.apps.userreports.const import UCR_ES_BACKEND, UCR_SQL_BACKEND, UCR_LABORATORY_BACKEND
from corehq.apps.userreports.data_source_providers import DynamicDataSourceProvider, StaticDataSourceProvider
from corehq.apps.userreports.exceptions import TableRebuildError, StaleRebuildError
from corehq.apps.userreports.sql import metadata
from corehq.apps.userreports.tasks import rebuild_indicators
from corehq.apps.userreports.util import get_indicator_adapter, get_backend_id
from corehq.sql_db.connections import connection_manager
from corehq.util.soft_assert import soft_assert
from fluff.signals import get_migration_context, get_tables_to_rebuild, reformat_alembic_diffs
from pillowtop.checkpoints.manager import PillowCheckpoint
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors import PillowProcessor
from pillowtop.utils import ensure_matched_revisions, ensure_document_exists
import six


REBUILD_CHECK_INTERVAL = 10 * 60  # in seconds
UCR_CHECKPOINT_ID = 'pillow-checkpoint-ucr-main'
UCR_STATIC_CHECKPOINT_ID = 'pillow-checkpoint-ucr-static'


class ConfigurableReportTableManagerMixin(object):

    def __init__(self, data_source_provider, auto_repopulate_tables=False, *args, **kwargs):
        self.bootstrapped = False
        self.last_bootstrapped = datetime.utcnow()
        self.data_source_provider = data_source_provider
        self.auto_repopulate_tables = auto_repopulate_tables
        super(ConfigurableReportTableManagerMixin, self).__init__(*args, **kwargs)

    def get_all_configs(self):
        return self.data_source_provider.get_data_sources()

    def needs_bootstrap(self):
        return (
            not self.bootstrapped
            or datetime.utcnow() - self.last_bootstrapped > timedelta(seconds=REBUILD_CHECK_INTERVAL)
        )

    def bootstrap_if_needed(self):
        if self.needs_bootstrap():
            self.bootstrap()

    def bootstrap(self, configs=None):
        # sets up the initial stuff
        if configs is None:
            configs = self.get_all_configs()

        self.table_adapters = [get_indicator_adapter(config, can_handle_laboratory=True) for config in configs]
        self.rebuild_tables_if_necessary()
        self.bootstrapped = True
        self.last_bootstrapped = datetime.utcnow()

    def rebuild_tables_if_necessary(self):
        sql_supported_backends = [UCR_SQL_BACKEND, UCR_LABORATORY_BACKEND]
        es_supported_backends = [UCR_ES_BACKEND, UCR_LABORATORY_BACKEND]
        self._rebuild_sql_tables(
            [a for a in self.table_adapters if get_backend_id(a.config) in sql_supported_backends])
        self._rebuild_es_tables(
            [a for a in self.table_adapters if get_backend_id(a.config) in es_supported_backends])

    def _rebuild_sql_tables(self, adapters):
        # todo move this code to sql adapter rebuild_if_necessary
        tables_by_engine = defaultdict(dict)
        for adapter in adapters:
            sql_adapter = get_indicator_adapter(adapter.config)
            tables_by_engine[sql_adapter.engine_id][sql_adapter.get_table().name] = sql_adapter

        _assert = soft_assert(to='@'.join(['czue', 'dimagi.com']))
        _notify_cory = lambda msg, obj: _assert(False, msg, obj)

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
                        rev_before_rebuild = sql_adapter.config.get_db().get_rev(sql_adapter.config._id)
                        self.rebuild_table(sql_adapter)
                    except TableRebuildError as e:
                        _notify_cory(six.text_type(e), sql_adapter.config.to_json())
                else:
                    self.rebuild_table(sql_adapter)

    def _rebuild_es_tables(self, adapters):
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

        for table in self.table_adapters:
            if table.config.domain == domain:
                # only bother getting the document if we have a domain match from the metadata
                doc = change.get_document()
                ensure_document_exists(change)
                ensure_matched_revisions(change)
                if table.config.filter(doc):
                    # best effort will swallow errors in the table
                    table.best_effort_save(doc)
                elif table.config.deleted_filter(doc):
                    table.delete(doc)


class ConfigurableReportKafkaPillow(ConstructedPillow):
    # the only reason this is a class is to avoid exposing _processor
    # for tests to be able to call bootstrap on it.
    # we could easily remove the class and push all the stuff in __init__ to
    # get_kafka_ucr_pillow below if we wanted.

    # don't retry errors until we figure out how to distinguish between
    # doc save errors and data source config errors
    retry_errors = False

    def __init__(self, processor, pillow_name):
        change_feed = KafkaChangeFeed(topics.ALL, group_id=pillow_name)
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
        assert self._processor is not None
        assert self._processor.bootstrapped is not None

    def bootstrap(self, configs=None):
        self._processor.bootstrap(configs)

    def rebuild_table(self, sql_adapter):
        self._processor.rebuild_table(sql_adapter)


def get_kafka_ucr_pillow(pillow_id='kafka-ucr-main'):
    return ConfigurableReportKafkaPillow(
        processor=ConfigurableReportPillowProcessor(
            data_source_provider=DynamicDataSourceProvider(),
            auto_repopulate_tables=False,
        ),
        pillow_name=pillow_id,
    )


def get_kafka_ucr_static_pillow(pillow_id='kafka-ucr-static'):
    return ConfigurableReportKafkaPillow(
        processor=ConfigurableReportPillowProcessor(
            data_source_provider=StaticDataSourceProvider(),
            auto_repopulate_tables=True,
        ),
        pillow_name=pillow_id,
    )
