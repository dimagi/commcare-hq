import os

from django.db import DEFAULT_DB_ALIAS
from django.test import SimpleTestCase
from django.test.utils import override_settings

from mock import patch
from nose.tools import assert_equal, assert_false, assert_true

from corehq.sql_db.config import PlProxyConfig, _get_standby_plproxy_config
from corehq.sql_db.connections import override_engine
from corehq.sql_db.routers import (
    READ_FROM_PLPROXY_STANDBYS,
    SYNCLOGS_APP,
    allow_migrate,
    allow_read_from_plproxy_standby,
    get_load_balanced_app_db,
    read_from_plproxy_standbys,
)
from corehq.sql_db.tests.test_connections import _get_db_config
from corehq.sql_db.tests.test_partition_config import (
    PARTITION_CONFIG_WITH_STANDBYS,
)
from corehq.sql_db.util import select_plproxy_db_for_read


class AllowMigrateTest(SimpleTestCase):

    @override_settings(
        SYNCLOGS_SQL_DB_ALIAS=DEFAULT_DB_ALIAS,
        USE_PARTITIONED_DATABASE=False,
        DATABASES={
            DEFAULT_DB_ALIAS: {},
            'synclogs': {
                'NAME': 'commcarehq_synclogs',
                'USER': 'commcarehq',
                'HOST': 'hqdb0', 'PORT': 5432
            },
        }
    )
    def test_synclogs_default(self):
        self.assertIs(True, allow_migrate(DEFAULT_DB_ALIAS, SYNCLOGS_APP))
        self.assertIs(False, allow_migrate('synclogs', SYNCLOGS_APP))

    @override_settings(
        SYNCLOGS_SQL_DB_ALIAS='synclogs',
        USE_PARTITIONED_DATABASE=True,
        DATABASES={
            DEFAULT_DB_ALIAS: {},
            'synclogs': {
                'NAME': 'commcarehq_synclogs',
                'USER': 'commcarehq',
                'HOST': 'hqdb0', 'PORT': 5432
            },
        }
    )
    def test_synclogs_db(self):
        self.assertIs(False, allow_migrate(DEFAULT_DB_ALIAS, SYNCLOGS_APP))
        self.assertIs(True, allow_migrate('synclogs', SYNCLOGS_APP))

    def test_icds_db_citus(self):
        with override_settings(CUSTOM_DB_ROUTING={}):
            self.assertIs(True, allow_migrate(DEFAULT_DB_ALIAS, 'icds_reports'))

        # map to reporting DB alias
        with override_settings(CUSTOM_DB_ROUTING={'custom_app': 'icds-ucr-citus'}), \
             override_engine('icds-ucr-citus', '', db_alias='icds-ucr'):
                self.assertIs(False, allow_migrate(DEFAULT_DB_ALIAS, 'custom_app'))
                self.assertIs(True, allow_migrate('icds-ucr', 'custom_app'))

        # map to DB alias
        with override_settings(CUSTOM_DB_ROUTING={'custom_app': 'icds-ucr'}):
            self.assertIs(True, allow_migrate('icds-ucr', 'custom_app'))

    @override_settings(DATABASES={'default': {}, 'synclogs': {}})
    def test_synclogs_non_partitioned(self):
        self.assertIs(False, allow_migrate('synclogs', 'accounting'))
        self.assertIs(True, allow_migrate(None, 'accounting'))
        self.assertIs(True, allow_migrate(DEFAULT_DB_ALIAS, 'accounting'))


@patch('corehq.sql_db.util.get_standby_databases', return_value=set())
@patch('corehq.sql_db.util.get_standbys_with_acceptible_delay', return_value=set())
def test_load_balanced_read_apps(_, __):
    load_balanced_apps = {
        'users': [
            ('users_db1', 5),
        ]
    }

    with override_settings(
        LOAD_BALANCED_APPS=load_balanced_apps,
        DATABASES={
            DEFAULT_DB_ALIAS: _get_db_config('default'),
            'users_db1': _get_db_config('users_db1')}):

        assert_equal(get_load_balanced_app_db('users', default="default_option"), 'users_db1')

    # If `LOAD_BALANCED_APPS` is not set for an app, it should point to default kwarg
    assert_equal(get_load_balanced_app_db('users', default='default_option'), 'default_option')


@override_settings(DATABASES=PARTITION_CONFIG_WITH_STANDBYS)
def test_load_balanced_plproxy():
    primary_config = PlProxyConfig.from_dict(PARTITION_CONFIG_WITH_STANDBYS)
    standby_config = _get_standby_plproxy_config(primary_config)

    master_standby_mapping = {
        'db1': {'db1_standby'},
        'db2': {'db2_standby'},
    }

    def _test_load_balanced_plproxy(primary_db, ok_standbys, expected_db):
        with patch('corehq.sql_db.util.plproxy_config', primary_config), \
             patch('corehq.sql_db.util.plproxy_standby_config', standby_config), \
             patch('corehq.sql_db.util.get_standbys_with_acceptible_delay', return_value=set(ok_standbys)), \
             patch('corehq.sql_db.util.primary_to_standbys_mapping', return_value=master_standby_mapping):

            db_for_read = select_plproxy_db_for_read(primary_db)
            assert_equal(db_for_read, expected_db)

    plproxy_shard_0 = primary_config.form_processing_dbs[0]
    plproxy_shard_0_standby = standby_config.form_processing_dbs[0]

    test_cases = [
        # (primary_db, standbys_with_acceptible_delay, expected_return_db)
        (primary_config.proxy_db, standby_config.form_processing_dbs, standby_config.proxy_db),
        (primary_config.proxy_db, standby_config.form_processing_dbs[0:1], primary_config.proxy_db),
        (primary_config.proxy_db, [], primary_config.proxy_db),
        (plproxy_shard_0, standby_config.form_processing_dbs, plproxy_shard_0_standby),
        (plproxy_shard_0, standby_config.form_processing_dbs[1:], plproxy_shard_0),
        (plproxy_shard_0, [], plproxy_shard_0),
    ]
    for case in test_cases:
        yield (_test_load_balanced_plproxy,) + case


def test_get_read_write_db_for_partitioned_model_decorator():
    @read_from_plproxy_standbys()
    def read():
        assert_true(allow_read_from_plproxy_standby())

    assert_false(allow_read_from_plproxy_standby())
    read()
    assert_false(allow_read_from_plproxy_standby())


def test_get_read_write_db_for_partitioned_model():
    test_cases = [
        patch.dict(os.environ, {READ_FROM_PLPROXY_STANDBYS: '1'}),
        read_from_plproxy_standbys(),
    ]
    for case in test_cases:
        yield _test_get_read_write_db_for_partitioned_model, case


def _test_get_read_write_db_for_partitioned_model(context):
    assert_false(allow_read_from_plproxy_standby())
    with context:
        assert_true(allow_read_from_plproxy_standby())
    assert_false(allow_read_from_plproxy_standby())
