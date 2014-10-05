from casexml.apps.case.models import CommCareCase
from corehq.apps.userreports.models import IndicatorConfiguration
from corehq.apps.userreports.sql import get_engine, IndicatorSqlAdapter
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

    def run(self):
        self.bootstrap()
        super(ConfigurableIndicatorPillow, self).run()

    def bootstrap(self, configs=None):
        # sets up the initial stuff
        if configs is None:
            configs = IndicatorConfiguration.all()

        self.tables = [IndicatorSqlAdapter(self.get_sql_engine(), config) for config in configs]
        self.bootstrapped = True

    def python_filter(self, doc):
        # filtering is done manually per indicator set change_transport
        return True

    def change_transport(self, doc):
        for table in self.tables:
            if table.config.filter.filter(doc):
                table.save(doc)
