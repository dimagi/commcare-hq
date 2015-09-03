from collections import defaultdict
from alembic.autogenerate.api import compare_metadata
from datetime import datetime, timedelta
from casexml.apps.case.models import CommCareCase
from corehq.apps.userreports.exceptions import TableRebuildError
from corehq.apps.userreports.models import DataSourceConfiguration, StaticDataSourceConfiguration
from corehq.apps.userreports.sql import IndicatorSqlAdapter, metadata
from corehq.apps.userreports.tasks import rebuild_indicators
from corehq.db import connection_manager
from dimagi.utils.logging import notify_error
from fluff.signals import get_migration_context, get_tables_to_rebuild
from pillowtop.couchdb import CachedCouchDB
from pillowtop.listener import PythonPillow


REBUILD_CHECK_INTERVAL = 10 * 60  # in seconds


class ConfigurableIndicatorPillow(PythonPillow):

    def __init__(self):
        # run_ptop never passes args to __init__ so make that explicit by not supporting any
        # todo: this will need to not be hard-coded if we ever split out forms and cases into their own domains
        couch_db = CachedCouchDB(CommCareCase.get_db().uri, readonly=False)
        super(ConfigurableIndicatorPillow, self).__init__(couch_db=couch_db)
        self.bootstrapped = False
        self.last_bootstrapped = datetime.utcnow()

    def get_all_configs(self):
        return DataSourceConfiguration.all()

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

        for engine_id, table_map in tables_by_engine.items():
            engine = connection_manager.get_engine(engine_id)
            with engine.begin() as connection:
                migration_context = get_migration_context(connection, table_map.keys())
                diffs = compare_metadata(migration_context, metadata)

            tables_to_rebuild = get_tables_to_rebuild(diffs, table_map.keys())
            for table_name in tables_to_rebuild:
                table = table_map[table_name]
                try:
                    self.rebuild_table(table)
                except TableRebuildError, e:
                    notify_error(unicode(e))

    def rebuild_table(self, table):
        table.rebuild_table()

    def python_filter(self, doc):
        # filtering is done manually per indicator see change_transport
        return True

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

    def set_checkpoint(self, change):
        # override this to rebootstrap the tables
        super(ConfigurableIndicatorPillow, self).set_checkpoint(change)


class StaticDataSourcePillow(ConfigurableIndicatorPillow):

    def get_all_configs(self):
        return StaticDataSourceConfiguration.all()

    def rebuild_table(self, table):
        super(StaticDataSourcePillow, self).rebuild_table(table)
        rebuild_indicators.delay(table.config.get_id)
