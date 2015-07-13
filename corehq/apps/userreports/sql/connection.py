import sqlalchemy
from django.conf import settings
from corehq.apps.userreports.models import DataSourceConfiguration


DEFAULT_ENGINE_ID = 'default'


def create_engine():
    return sqlalchemy.create_engine(settings.SQL_REPORTING_DATABASE_URL)


class ConnectionManager(object):
    """
    Object for dealing with connections.
    """

    def __init__(self):
        self._engines = {}

    def get_engine(self, engine_id=DEFAULT_ENGINE_ID):
        """
        Get an engine by ID. This should be a unique field identifying the connection,
        e.g. "report-db-1"
        """
        if engine_id not in self._engines:
            engine = create_engine()
            self._engines[engine_id] = engine

        return self._engines[engine_id]

    def dispose_engine(self, engine_id=DEFAULT_ENGINE_ID):
        """
        If found, disposes an engine and removes it from this, otherwise does nothing.
        """
        if engine_id in self._engines:
            engine = self._engines.pop(engine_id)
            engine.dispose()

    def dispose_all(self):
        """
        Dispose all engines associated with this. Useful for tests.
        """
        for engine_id in self._engines:
            self.dispose_engine(engine_id)

    def _get_connection_string(self, engine_id):
        # for now this just always returns the same connection string for any
        # engine_id, but in the future we could make this function more complicated
        return {
            DEFAULT_ENGINE_ID: settings.SQL_REPORTING_DATABASE_URL
        }.get(engine_id, settings.SQL_REPORTING_DATABASE_URL)


def get_engine_id(object):
    """
    Given an object, get the engine id for it.
    """
    # for now this only deals with data sources.
    assert isinstance(object, DataSourceConfiguration)
    # we can swap this out to specify multiple engines when we want to support multiple databases/schemas
    return DEFAULT_ENGINE_ID


connection_manager = ConnectionManager()
