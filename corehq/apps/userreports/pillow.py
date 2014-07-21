from corehq.apps.userreports.models import IndicatorConfiguration
from corehq.apps.userreports.sql import get_engine, IndicatorSqlAdapter
from pillowtop.listener import PythonPillow


class ConfigurableIndicatorPillow(PythonPillow):

    def __init__(self):
        # config should be an of IndicatorConfiguration document.
        # todo: should this be a list of configs or some other relationship?
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
