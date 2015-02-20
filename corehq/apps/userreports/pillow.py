from alembic.autogenerate.api import compare_metadata
from casexml.apps.case.models import CommCareCase
from corehq.apps.userreports.models import DataSourceConfiguration, CustomDataSourceConfiguration
from corehq.apps.userreports.sql import get_engine, IndicatorSqlAdapter, metadata
from corehq.apps.userreports.tasks import rebuild_indicators
from fluff.signals import get_migration_context, get_tables_to_rebuild
from pillowtop.couchdb import CachedCouchDB
from pillowtop.listener import PythonPillow


class ConfigurableIndicatorPillow(PythonPillow):

    def __init__(self):
        # run_ptop never passes args to __init__ so make that explicit by not supporting any
        # todo: this will need to not be hard-coded if we ever split out forms and cases into their own domains
        couch_db = CachedCouchDB(CommCareCase.get_db().uri, readonly=False)
        super(ConfigurableIndicatorPillow, self).__init__(couch_db=couch_db)
        self.bootstrapped = False

    @classmethod
    def get_sql_engine(cls):
        # todo: copy pasted from fluff - cleanup
        engine = getattr(cls, '_engine', None)
        if not engine:
            cls._engine = get_engine()
        return cls._engine

    def get_all_configs(self):
        return DataSourceConfiguration.all()

    def run(self):
        self.bootstrap()
        super(ConfigurableIndicatorPillow, self).run()

    def bootstrap(self, configs=None):
        # sets up the initial stuff
        if configs is None:
            configs = self.get_all_configs()

        self.tables = [IndicatorSqlAdapter(self.get_sql_engine(), config) for config in configs]
        self.rebuild_tables_if_necessary()
        self.bootstrapped = True

    def rebuild_tables_if_necessary(self):
        table_map = {t.get_table().name: t for t in self.tables}
        engine = self.get_sql_engine()
        with engine.begin() as connection:
            migration_context = get_migration_context(connection, table_map.keys())
            diffs = compare_metadata(migration_context, metadata)

        tables_to_rebuild = get_tables_to_rebuild(diffs, table_map.keys())
        for table_name in tables_to_rebuild:
            table = table_map[table_name]
            self.rebuild_table(table)

    def rebuild_table(self, table):
        table.rebuild_table()

    def python_filter(self, doc):
        # filtering is done manually per indicator set change_transport
        return True

    def change_transport(self, doc):
        if not self.bootstrapped:
            self.bootstrap()
        for table in self.tables:
            if table.config.filter(doc):
                table.save(doc)
            elif table.config.deleted_filter(doc):
                table.delete(doc)

    def set_checkpoint(self, change):
        # override this to rebootstrap the tables
        super(ConfigurableIndicatorPillow, self).set_checkpoint(change)

        # todo: may want to consider adjusting the frequency or using another mechanism for this
        self.bootstrap()


class CustomDataSourcePillow(ConfigurableIndicatorPillow):

    def get_all_configs(self):
        return CustomDataSourceConfiguration.all()

    def rebuild_table(self, table):
        super(CustomDataSourcePillow, self).rebuild_table(table)
        rebuild_indicators.delay(table.config.get_id)
