from contextlib import contextmanager

from django.conf import settings
import sqlalchemy
from sqlalchemy.orm.scoping import scoped_session
from sqlalchemy.orm.session import sessionmaker
from django.core import signals

DEFAULT_ENGINE_ID = 'default'
UCR_ENGINE_ID = 'ucr'
ICDS_UCR_ENGINE_ID = 'icds-ucr'
ICDS_TEST_UCR_ENGINE_ID = 'icds-test-ucr'


def create_engine(connection_string):
    # paramstyle='format' allows you to use column names that include the ')' character
    # otherwise queries will sometimes be misformated/error when formatting
    # https://github.com/zzzeek/sqlalchemy/blob/ff20903/lib/sqlalchemy/dialects/postgresql/psycopg2.py#L173
    return sqlalchemy.create_engine(connection_string, paramstyle='format')


class SessionHelper(object):
    """
    Shim class helper for a single connection/session factory
    """

    def __init__(self, connection_string):
        self.engine = create_engine(connection_string)
        self._session_factory = sessionmaker(bind=self.engine)
        # Session is the actual constructor object
        self.Session = scoped_session(self._session_factory)

    @property
    def session_context(self):
        @contextmanager
        def session_scope():
            """Provide a transactional scope around a series of operations."""
            session = self.Session()
            try:
                yield session
                session.commit()
            except:
                session.rollback()
                raise
            finally:
                session.close()

        return session_scope


class ConnectionManager(object):
    """
    Object for dealing with sqlalchemy engines and sessions.
    """

    def __init__(self):
        self._session_helpers = {}
        self.db_connection_map = {
            DEFAULT_ENGINE_ID: settings.SQL_REPORTING_DATABASE_URL,
            UCR_ENGINE_ID: settings.UCR_DATABASE_URL,
        }
        self._populate_connection_map()

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
        connection_string = self.db_connection_map.get(engine_id)
        return connection_string or self.db_connection_map['default']

    def _populate_connection_map(self):
        self._add_django_db(ICDS_UCR_ENGINE_ID, 'ICDS_UCR_DATABASE_ALIAS')
        self._add_django_db(ICDS_TEST_UCR_ENGINE_ID, 'ICDS_UCR_TEST_DATABASE_ALIAS')
        for custom_engine_id, custom_db_url in settings.CUSTOM_DATABASES:
            self.db_connection_map[custom_engine_id] = custom_db_url

    def _add_django_db(self, engine_id, django_db_alias):
        if self._django_db_exists(django_db_alias):
            connection_string = self._connection_string_from_django(settings.ICDS_UCR_DATABASE_ALIAS)
            self.db_connection_map[engine_id] = connection_string

    def _connection_string_from_django(self, django_alias):
        return "postgresql+psycopg2://{USER}:{PASSWORD}@{HOST}:{PORT}/{NAME}".format(
                **settings.DATABASES[django_alias]
            )

    def _django_db_exists(self, django_alias):
        return getattr(settings, django_alias, None) in settings.DATABASES

connection_manager = ConnectionManager()
Session = connection_manager.get_scoped_session(DEFAULT_ENGINE_ID)


# Register an event that closes the database connection
# when a Django request is finished.
# This will rollback any open transactions.
def _close_connections(**kwargs):
    Session.remove()  # todo: unclear whether this is necessary
    connection_manager.close_scoped_sessions()

signals.request_finished.connect(_close_connections)


@contextmanager
def override_engine(engine_id, connection_url):
    original_url = connection_manager.get_connection_string(engine_id)
    connection_manager.db_connection_map[engine_id] = connection_url
    try:
        yield
    finally:
        connection_manager.db_connection_map[engine_id] = original_url
