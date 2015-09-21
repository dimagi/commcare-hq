from django.conf import settings
import sqlalchemy
from sqlalchemy.orm.scoping import scoped_session
from sqlalchemy.orm.session import sessionmaker
from django.core import signals

DEFAULT_ENGINE_ID = 'default'
UCR_ENGINE_ID = 'ucr'


def create_engine(connection_string=None):
    # todo: this function is just a proxy for the sqlalchemy version and should be removed
    connection_string = connection_string or settings.SQL_REPORTING_DATABASE_URL
    return sqlalchemy.create_engine(connection_string)


class SessionHelper(object):
    """
    Shim class helper for a single connection/session factory
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
        self._session_helpers = {}

    def _get_or_create_helper(self, engine_id):
        if engine_id not in self._session_helpers:
            self._session_helpers[engine_id] = SessionHelper(self.get_connection_string(engine_id))
        return self._session_helpers[engine_id]

    def get_session_helper(self, engine_id=DEFAULT_ENGINE_ID):
        """
        Returns the SessionHelper object associated with this engine id
        """
        # making this separate from _get_or_create in case we ever want to fail differently here
        return self._get_or_create_helper(engine_id)

    def get_scoped_session(self, engine_id=DEFAULT_ENGINE_ID):
        """
        This returns a handle to a thread-locally scoped session object.
        """
        return self.get_session_helper(engine_id).Session

    def get_engine(self, engine_id=DEFAULT_ENGINE_ID):
        """
        Get an engine by ID. This should be a unique field identifying the connection,
        e.g. "report-db-1"
        """
        return self._get_or_create_helper(engine_id).engine

    def close_scoped_sessions(self):
        for helper in self._session_helpers.values():
            helper.Session.remove()

    def dispose_engine(self, engine_id=DEFAULT_ENGINE_ID):
        """
        If found, closes the active sessions associated with an an engine and disposes it.
        Also removes it from the session manager.
        If not found, does nothing.
        """
        if engine_id in self._session_helpers:
            helper = self._session_helpers.pop(engine_id)
            helper.Session.remove()
            helper.engine.dispose()

    def dispose_all(self):
        """
        Dispose all engines associated with this. Useful for tests.
        """
        for engine_id in self._session_helpers.keys():
            self.dispose_engine(engine_id)

    def get_connection_string(self, engine_id):
        # for now this just always returns the same connection string for any
        # engine_id, but in the future we could make this function more complicated
        return {
            DEFAULT_ENGINE_ID: settings.SQL_REPORTING_DATABASE_URL,
            UCR_ENGINE_ID: settings.UCR_DATABASE_URL,
        }.get(engine_id, settings.SQL_REPORTING_DATABASE_URL)


connection_manager = ConnectionManager()
Session = connection_manager.get_scoped_session(DEFAULT_ENGINE_ID)


# Register an event that closes the database connection
# when a Django request is finished.
# This will rollback any open transactions.
def _close_connections(**kwargs):
    Session.remove()  # todo: unclear whether this is necessary
    connection_manager.close_scoped_sessions()

signals.request_finished.connect(_close_connections)
