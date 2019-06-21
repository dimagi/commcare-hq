from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals

from contextlib import contextmanager

import sqlalchemy
from django.conf import settings
from django.core import signals
from django.utils.functional import cached_property
from six.moves.urllib.parse import urlencode
from sqlalchemy.orm.scoping import scoped_session
from sqlalchemy.orm.session import sessionmaker

from corehq.util.test_utils import unit_testing_only
from .util import select_db_for_read

DEFAULT_ENGINE_ID = 'default'
UCR_ENGINE_ID = 'ucr'
ICDS_UCR_ENGINE_ID = 'icds-ucr'
ICDS_UCR_NON_DASHBOARD_ENGINE_ID = 'icds-ucr-non-dashboard'
AAA_DB_ENGINE_ID = 'aaa-data'
ICDS_UCR_CITUS_ENGINE_ID = 'icds-ucr-citus'


def get_icds_ucr_db_alias_or_citus(force_citus):
    return get_icds_ucr_citus_db_alias() if force_citus else get_icds_ucr_db_alias()


def get_icds_ucr_db_alias():
    return _get_db_alias_or_none(ICDS_UCR_ENGINE_ID)


def get_icds_ucr_citus_db_alias():
    return _get_db_alias_or_none(ICDS_UCR_CITUS_ENGINE_ID)


def get_aaa_db_alias():
    return _get_db_alias_or_none(AAA_DB_ENGINE_ID)


def _get_db_alias_or_none(enigne_id):
    try:
        return connection_manager.get_django_db_alias(enigne_id)
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

    @cached_property
    def is_citus_db(self):
        with self.engine.begin() as connection:
            return is_citus_db(connection)


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

    def engine_id_is_available(self, engine_id):
        return engine_id in self.engine_id_django_db_map

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

    def get_load_balanced_read_db_alias(self, engine_id, default=None):
        """
        returns the load balanced read db alias based on list of read databases
            and their weights obtained from settings.REPORTING_DATABASES and
            settings.LOAD_BALANCED_APPS.

            If a suitable db is not found returns the `default` or `engine_id` itself
        """
        read_dbs = self.read_database_mapping.get(engine_id, [])
        load_balanced_db = select_db_for_read(read_dbs)

        return load_balanced_db or default or engine_id

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
        for engine_id in list(self._session_helpers.keys()):
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
                weighted_read_dbs = None
                if isinstance(db_config, dict):
                    write_db = db_config['WRITE']
                    weighted_read_dbs = db_config['READ']
                    dbs = [db for db, weight in weighted_read_dbs]
                    assert set(dbs).issubset(set(settings.DATABASES))

                self._add_django_db(engine_id, write_db)
                if weighted_read_dbs:
                    self.read_database_mapping[engine_id] = weighted_read_dbs
                    for read_db, weighting in weighted_read_dbs:
                        assert read_db == write_db or read_db not in self.db_connection_map, read_db
                        if read_db != write_db:
                            self._add_django_db(read_db, read_db)

        for app, weighted_read_dbs in settings.LOAD_BALANCED_APPS.items():
            self.read_database_mapping[app] = weighted_read_dbs
            dbs = [db for db, weight in weighted_read_dbs]
            assert set(dbs).issubset(set(settings.DATABASES))

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

    def resolves_to_unique_dbs(self, engine_ids):
        # return True if all in the list of engine_ids point to a different database
        return len(engine_ids) == len({connection_manager.get_django_db_alias(e) for e in engine_ids})


connection_manager = ConnectionManager()
Session = connection_manager.get_scoped_session(DEFAULT_ENGINE_ID)


# Register an event that closes the database connection
# when a Django request is finished.
# This will rollback any open transactions.
def _close_connections(**kwargs):
    Session.remove()  # todo: unclear whether this is necessary
    connection_manager.close_scoped_sessions()

signals.request_finished.connect(_close_connections)


@unit_testing_only
@contextmanager
def override_engine(engine_id, connection_url, db_alias=None):
    original_url = connection_manager.get_connection_string(engine_id)
    original_alias = connection_manager.engine_id_django_db_map.get(engine_id, None)
    connection_manager.db_connection_map[engine_id] = connection_url
    if db_alias:
        connection_manager.engine_id_django_db_map[engine_id] = db_alias
    try:
        yield
    finally:
        connection_manager.db_connection_map[engine_id] = original_url
        connection_manager.engine_id_django_db_map[engine_id] = original_alias


def is_citus_db(connection):
    """
    :param connection: either a sqlalchemy connection or a Django cursor
    """
    res = connection.execute("SELECT 1 FROM pg_extension WHERE extname = 'citus'")
    if res is None:
        res = list(connection)
    return bool(list(res))
