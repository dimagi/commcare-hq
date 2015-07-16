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


class SessionFactory(object):
    """
    Shim class for a single connection/session factory
    """

    def __init__(self, connection_string):
        self.engine = create_engine(connection_string)
        self._session_factory = sessionmaker(bind=self.engine)
        # Session is the actual constructor object
        self.Session = scoped_session(self._session_factory)


class ConnectionManager(object):
    """
    Object for dealing with sqlalchemy engines and sessions.
    """

    def __init__(self):
        self._session_factories = {}

    def _get_or_create_factory(self, engine_id):
        if engine_id not in self._session_factories:
            self._session_factories[engine_id] = SessionFactory(self._get_connection_string(engine_id))
        return self._session_factories[engine_id]

    def get_session_constructor(self, engine_id=DEFAULT_ENGINE_ID):
        """
        This returns a class that can be instantiated and will have a session scoped
        to the local thread.
        """
        return self._get_or_create_factory(engine_id).Session

    def get_engine(self, engine_id=DEFAULT_ENGINE_ID):
        """
        Get an engine by ID. This should be a unique field identifying the connection,
        e.g. "report-db-1"
        """
        return self._get_or_create_factory(engine_id).engine

    def dispose_engine(self, engine_id=DEFAULT_ENGINE_ID):
        """
        If found, disposes an engine and removes it from this, otherwise does nothing.
        """
        if engine_id in self._session_factories:
            factory = self._session_factories.pop(engine_id)
            factory.engine.dispose()

    def dispose_all(self):
        """
        Dispose all engines associated with this. Useful for tests.
        """
        for engine_id in self._session_factories.keys():
            self.dispose_engine(engine_id)

    def _get_connection_string(self, engine_id):
        # for now this just always returns the same connection string for any
        # engine_id, but in the future we could make this function more complicated
        return {
            DEFAULT_ENGINE_ID: settings.SQL_REPORTING_DATABASE_URL
        }.get(engine_id, settings.SQL_REPORTING_DATABASE_URL)


connection_manager = ConnectionManager()
Session = connection_manager.get_session_constructor(DEFAULT_ENGINE_ID)


# Register an event that closes the database connection
# when a Django request is finished.
# This will rollback any open transactions.
def _close_connection(**kwargs):
    Session.remove()

signals.request_finished.connect(_close_connection)
