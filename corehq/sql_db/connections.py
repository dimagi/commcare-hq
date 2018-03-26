from __future__ import absolute_import
from __future__ import unicode_literals
import random
from contextlib import contextmanager
from six.moves.urllib.parse import urlencode

from django.conf import settings
import sqlalchemy
from sqlalchemy.orm.scoping import scoped_session
from sqlalchemy.orm.session import sessionmaker
from django.core import signals

DEFAULT_ENGINE_ID = 'default'
UCR_ENGINE_ID = 'ucr'
ICDS_UCR_ENGINE_ID = 'icds-ucr'
ICDS_TEST_UCR_ENGINE_ID = 'icds-test-ucr'


def get_icds_ucr_db_alias():
    try:
        return connection_manager.get_django_db_alias(ICDS_UCR_ENGINE_ID)
    except KeyError:
        return None


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
        self.db_connection_map = {}
        self.read_database_mapping = {}
        self.engine_id_django_db_map = {}
        self._populate_connection_map()

    def _get_or_create_helper(self, engine_id):
        if engine_id not in self._session_helpers:
            self._session_helpers[engine_id] = SessionHelper(self.get_connection_string(engine_id))
        return self._session_helpers[engine_id]

    def get_django_db_alias(self, engine_id):
        return self.engine_id_django_db_map[engine_id]

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

    def get_load_balanced_read_engine_id(self, engine_id):
        read_dbs = self.read_database_mapping.get(engine_id, [])
        if read_dbs:
            return random.choice(read_dbs)
        return engine_id

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
        reporting_db_config = self._get_reporting_db_config()
        if not reporting_db_config:
            self._populate_from_legacy_settings()
        else:
            for engine_id, db_config in reporting_db_config.items():
                write_db = db_config
                read = None
                if isinstance(db_config, dict):
                    write_db = db_config['WRITE']
                    read = db_config['READ']
                    for db_alias, weighting in read:
                        assert isinstance(weighting, int), 'weighting must be int'
                        assert db_alias in settings.DATABASES, db_alias

                self._add_django_db(engine_id, write_db)
                if read:
                    self.read_database_mapping[engine_id] = []
                    for read_db, weighting in read:
                        assert read_db == write_db or read_db not in self.db_connection_map, read_db
                        self.read_database_mapping[engine_id].extend([read_db] * weighting)
                        if read_db != write_db:
                            self._add_django_db(read_db, read_db)

        if DEFAULT_ENGINE_ID not in self.db_connection_map:
            self._add_django_db(DEFAULT_ENGINE_ID, 'default')
        if UCR_ENGINE_ID not in self.db_connection_map:
            self._add_django_db(UCR_ENGINE_ID, 'default')

    def _populate_from_legacy_settings(self):
        default_db = self._connection_string_from_django('default')
        ucr_db_reporting_url = getattr(settings, 'UCR_DATABASE_URL', None)
        self.db_connection_map[DEFAULT_ENGINE_ID] = default_db
        self.db_connection_map[UCR_ENGINE_ID] = ucr_db_reporting_url or default_db

    def _get_reporting_db_config(self):
        return getattr(settings, 'REPORTING_DATABASES', None)

    def _add_django_db_from_settings_key(self, engine_id, db_alias_settings_key):
        db_alias = self._get_db_alias_from_settings_key(db_alias_settings_key)
        if db_alias:
            self._add_django_db(engine_id, db_alias)

    def _add_django_db(self, engine_id, db_alias):
        self.engine_id_django_db_map[engine_id] = db_alias
        connection_string = self._connection_string_from_django(db_alias)
        self.db_connection_map[engine_id] = connection_string

    def _connection_string_from_django(self, django_alias):
        db_settings = settings.DATABASES[django_alias].copy()
        db_settings['PORT'] = db_settings.get('PORT', '5432')
        options = db_settings.get('OPTIONS')
        db_settings['OPTIONS'] = '?{}'.format(urlencode(options)) if options else ''

        return "postgresql+psycopg2://{USER}:{PASSWORD}@{HOST}:{PORT}/{NAME}{OPTIONS}".format(
            **db_settings
        )

    def _get_db_alias_from_settings_key(self, db_alias_settings_key):
        db_alias = getattr(settings, db_alias_settings_key, None)
        if db_alias in settings.DATABASES:
            return db_alias


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
