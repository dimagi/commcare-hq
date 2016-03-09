from collections import defaultdict
from alembic.autogenerate.api import compare_metadata
from datetime import datetime, timedelta
from casexml.apps.case.models import CommCareCase
from corehq.apps.change_feed import topics
from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed, MultiTopicCheckpointEventHandler
from corehq.apps.userreports.data_source_providers import DynamicDataSourceProvider, StaticDataSourceProvider
from corehq.apps.userreports.exceptions import TableRebuildError, StaleRebuildError
from corehq.apps.userreports.sql import IndicatorSqlAdapter, metadata
from corehq.apps.userreports.tasks import is_static, rebuild_indicators
from corehq.sql_db.connections import connection_manager
from corehq.toggles import KAFKA_UCRS
from corehq.util.soft_assert import soft_assert
from fluff.signals import get_migration_context, get_tables_to_rebuild
from pillowtop.checkpoints.manager import PillowCheckpoint
from pillowtop.couchdb import CachedCouchDB
from pillowtop.listener import PythonPillow
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors import PillowProcessor


REBUILD_CHECK_INTERVAL = 10 * 60  # in seconds
UCR_CHECKPOINT_ID = 'pillow-checkpoint-ucr-main'
UCR_STATIC_CHECKPOINT_ID = 'pillow-checkpoint-ucr-static'


class ConfigurableReportTableManagerMixin(object):

    def __init__(self, data_source_provider, *args, **kwargs):
        self.bootstrapped = False
        self.last_bootstrapped = datetime.utcnow()
        self.data_source_provider = data_source_provider
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

        self.table_adapters = [IndicatorSqlAdapter(config) for config in configs]
        self.rebuild_tables_if_necessary()
        self.bootstrapped = True
        self.last_bootstrapped = datetime.utcnow()

    def rebuild_tables_if_necessary(self):
        tables_by_engine = defaultdict(dict)
        for adapter in self.table_adapters:
            tables_by_engine[adapter.engine_id][adapter.get_table().name] = adapter

        _assert = soft_assert(to='@'.join(['czue', 'dimagi.com']))
        _notify_cory = lambda msg, obj: _assert(False, msg, obj)

        for engine_id, table_map in tables_by_engine.items():
            engine = connection_manager.get_engine(engine_id)
            with engine.begin() as connection:
                migration_context = get_migration_context(connection, table_map.keys())
                diffs = compare_metadata(migration_context, metadata)

            tables_to_rebuild = get_tables_to_rebuild(diffs, table_map.keys())
            for table_name in tables_to_rebuild:
                sql_adapter = table_map[table_name]
                if not is_static(sql_adapter.config._id):
                    try:
                        rev_before_rebuild = sql_adapter.config.get_db().get_rev(sql_adapter.config._id)
                        self.rebuild_table(sql_adapter)
                    except TableRebuildError, e:
                        _notify_cory(unicode(e), sql_adapter.config.to_json())
                    else:
                        # note: this fancy logging can be removed as soon as we get to the
                        # bottom of http://manage.dimagi.com/default.asp?211297
                        # if no signs of it popping back up by april 2016, should remove this
                        rev_after_rebuild = sql_adapter.config.get_db().get_rev(sql_adapter.config._id)
                        _notify_cory(
                            u'rebuilt table {} ({}) because {}. rev before: {}, rev after: {}'.format(
                                table_name,
                                u'{} [{}]'.format(sql_adapter.config.display_name, sql_adapter.config._id),
                                diffs,
                                rev_before_rebuild,
                                rev_after_rebuild,
                            ),
                            sql_adapter.config.to_json(),
                        )
                else:
                    self.rebuild_table(sql_adapter)

    def rebuild_table(self, sql_adapter):
        config = sql_adapter.config
        if not is_static(config._id):
            latest_rev = config.get_db().get_rev(config._id)
            if config._rev != latest_rev:
                raise StaleRebuildError('Tried to rebuild a stale table ({})! Ignoring...'.format(config))
        sql_adapter.rebuild_table()


class ConfigurableIndicatorPillow(ConfigurableReportTableManagerMixin, PythonPillow):

    def __init__(self, data_source_provider=None, pillow_checkpoint_id=UCR_CHECKPOINT_ID):
        # todo: this will need to not be hard-coded if we ever split out forms and cases into their own databases
        couch_db = CachedCouchDB(CommCareCase.get_db().uri, readonly=False)
        checkpoint = PillowCheckpoint(pillow_checkpoint_id)
        if data_source_provider is None:
            data_source_provider = DynamicDataSourceProvider()
        super(ConfigurableIndicatorPillow, self).__init__(
            data_source_provider=data_source_provider,
            couch_db=couch_db,
            checkpoint=checkpoint,
        )

    def run(self):
        self.bootstrap()
        super(ConfigurableIndicatorPillow, self).run()

    def change_trigger(self, changes_dict):
        self.bootstrap_if_needed()
        if changes_dict.get('deleted', False):
            # we don't currently support hard-deletions at all.
            # we may want to change this at some later date but seem ok for now.
            # see https://github.com/dimagi/commcare-hq/pull/6944 for rationale
            pass
        return super(ConfigurableIndicatorPillow, self).change_trigger(changes_dict)

    def change_transport(self, doc):
        domain = doc.get('domain', None)
        # domains with kafka ucrs enabled should be processed by the other pillow
        if KAFKA_UCRS.enabled(domain):
            return

        for table in self.table_adapters:
            if table.config.filter(doc):
                table.save(doc)
            elif table.config.deleted_filter(doc):
                table.delete(doc)


class StaticDataSourcePillow(ConfigurableIndicatorPillow):

    def __init__(self):
        super(StaticDataSourcePillow, self).__init__(
            data_source_provider=StaticDataSourceProvider(),
            pillow_checkpoint_id=UCR_STATIC_CHECKPOINT_ID,
        )

    def rebuild_table(self, sql_adapter):
        super(StaticDataSourcePillow, self).rebuild_table(sql_adapter)
        rebuild_indicators.delay(sql_adapter.config.get_id)


class ConfigurableReportPillowProcessor(ConfigurableReportTableManagerMixin, PillowProcessor):

    def process_change(self, pillow_instance, change, do_set_checkpoint):
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
            if table.config.domain == domain and KAFKA_UCRS.enabled(domain):
                # only bother getting the document if we have a domain match from the metadata
                doc = change.get_document()
                if table.config.filter(doc):
                    table.save(doc)
                elif table.config.deleted_filter(doc):
                    table.delete(doc)


class ConfigurableReportKafkaPillow(ConstructedPillow):
    # the only reason this is a class is to avoid exposing _processor
    # for tests to be able to call bootstrap on it.
    # we could easily remove the class and push all the stuff in __init__ to
    # get_kafka_ucr_pillow below if we wanted.

    def __init__(self, data_source_provider, pillow_name):
        change_feed = KafkaChangeFeed(topics.ALL, group_id=pillow_name)
        checkpoint = PillowCheckpoint(pillow_name)
        event_handler = MultiTopicCheckpointEventHandler(
            checkpoint=checkpoint, checkpoint_frequency=1000, change_feed=change_feed
        )
        super(ConfigurableReportKafkaPillow, self).__init__(
            name=pillow_name,
            document_store=None,
            change_feed=change_feed,
            processor=ConfigurableReportPillowProcessor(data_source_provider),
            checkpoint=checkpoint,
            change_processed_event_handler=event_handler
        )
        # set by the superclass constructor
        assert self._processor is not None
        assert self._processor.bootstrapped is not None

    def bootstrap(self, configs=None):
        self._processor.bootstrap(configs)


def get_kafka_ucr_pillow():
    return ConfigurableReportKafkaPillow(
        data_source_provider=DynamicDataSourceProvider(), pillow_name='kafka-ucr-main'
    )


def get_kafka_ucr_static_pillow():
    return ConfigurableReportKafkaPillow(
        data_source_provider=StaticDataSourceProvider(), pillow_name='kafka-ucr-static'
    )
