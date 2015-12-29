from collections import defaultdict
from alembic.autogenerate.api import compare_metadata
from datetime import datetime, timedelta
from casexml.apps.case.models import CommCareCase
from corehq.apps.userreports.exceptions import TableRebuildError, StaleRebuildError
from corehq.apps.userreports.models import DataSourceConfiguration, StaticDataSourceConfiguration
from corehq.apps.userreports.sql import IndicatorSqlAdapter, metadata
from corehq.apps.userreports.tasks import rebuild_indicators
from corehq.sql_db.connections import connection_manager
from corehq.util.soft_assert import soft_assert
from fluff.signals import get_migration_context, get_tables_to_rebuild
from pillowtop.checkpoints.manager import PillowCheckpoint, get_django_checkpoint_store
from pillowtop.couchdb import CachedCouchDB
from pillowtop.listener import PythonPillow


REBUILD_CHECK_INTERVAL = 10 * 60  # in seconds
UCR_CHECKPOINT_ID = 'pillow-checkpoint-ucr-main'
UCR_STATIC_CHECKPOINT_ID = 'pillow-checkpoint-ucr-static'


class ConfigurableIndicatorPillow(PythonPillow):

    def __init__(self, pillow_checkpoint_id=UCR_CHECKPOINT_ID):
        # todo: this will need to not be hard-coded if we ever split out forms and cases into their own domains
        couch_db = CachedCouchDB(CommCareCase.get_db().uri, readonly=False)
        checkpoint = PillowCheckpoint(get_django_checkpoint_store(), pillow_checkpoint_id)
        super(ConfigurableIndicatorPillow, self).__init__(couch_db=couch_db, checkpoint=checkpoint)
        self.bootstrapped = False
        self.last_bootstrapped = datetime.utcnow()

    def get_all_configs(self):
        return filter(lambda config: config.is_active, DataSourceConfiguration.all())

    def run(self):
        self.bootstrap()
        super(ConfigurableIndicatorPillow, self).run()

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
        _notify_cory = lambda msg: _assert(False, msg)

        for engine_id, table_map in tables_by_engine.items():
            engine = connection_manager.get_engine(engine_id)
            with engine.begin() as connection:
                migration_context = get_migration_context(connection, table_map.keys())
                diffs = compare_metadata(migration_context, metadata)

            tables_to_rebuild = get_tables_to_rebuild(diffs, table_map.keys())
            for table_name in tables_to_rebuild:
                sql_adapter = table_map[table_name]
                try:
                    self.rebuild_table(sql_adapter)
                except TableRebuildError, e:
                    _notify_cory(unicode(e))
                else:
                    _notify_cory(u'rebuilt table {} ({}) because {}'.format(
                        table_name,
                        u'{} [{}]'.format(sql_adapter.config.display_name, sql_adapter.config._id),
                        diffs,
                    ))

    def rebuild_table(self, sql_adapter):
        config = sql_adapter.config
        latest_rev = config.get_db().get_rev(config._id)
        if config._rev != latest_rev:
            raise StaleRebuildError('Tried to rebuild a stale table ({})! Ignoring...'.format(config))
        sql_adapter.rebuild_table()

    def change_trigger(self, changes_dict):
        self.bootstrap_if_needed()
        if changes_dict.get('deleted', False):
            # we don't currently support hard-deletions at all.
            # we may want to change this at some later date but seem ok for now.
            # see https://github.com/dimagi/commcare-hq/pull/6944 for rationale
            pass
        return super(ConfigurableIndicatorPillow, self).change_trigger(changes_dict)

    def change_transport(self, doc):
        for table in self.table_adapters:
            if table.config.filter(doc):
                table.save(doc)
            elif table.config.deleted_filter(doc):
                table.delete(doc)


class StaticDataSourcePillow(ConfigurableIndicatorPillow):

    def __init__(self):
        super(StaticDataSourcePillow, self).__init__(pillow_checkpoint_id=UCR_STATIC_CHECKPOINT_ID)

    def get_all_configs(self):
        return StaticDataSourceConfiguration.all()

    def rebuild_table(self, sql_adapter):
        super(StaticDataSourcePillow, self).rebuild_table(sql_adapter)
        rebuild_indicators.delay(sql_adapter.config.get_id)
