from django.conf import settings
import sqlalchemy
from sqlalchemy.orm.scoping import scoped_session
from sqlalchemy.orm.session import sessionmaker
from django.core import signals

DEFAULT_ENGINE_ID = 'default'


def create_engine(connection_string=None):
    # todo: this function is just a proxy for the sqlalchemy version and should be removed
    connection_string = connection_string or settings.SQL_REPORTING_DATABASE_URL
    return sqlalchemy.create_engine(connection_string)


class ConnectionManager(object):
    """
    Object for dealing with sqlalchemy engines and sessions.
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
        for engine_id in self._engines.keys():
            self.dispose_engine(engine_id)

    def _get_connection_string(self, engine_id):
        # for now this just always returns the same connection string for any
        # engine_id, but in the future we could make this function more complicated
        return {
            DEFAULT_ENGINE_ID: settings.SQL_REPORTING_DATABASE_URL
        }.get(engine_id, settings.SQL_REPORTING_DATABASE_URL)


connection_manager = ConnectionManager()
_engine = create_engine(settings.SQL_REPORTING_DATABASE_URL)
_session_factory = sessionmaker(bind=_engine)

Session = scoped_session(_session_factory)


# Register an event that closes the database connection
# when a Django request is finished.
# This will rollback any open transactions.
def _close_connection(**kwargs):
    Session.remove()

signals.request_finished.connect(_close_connection)
