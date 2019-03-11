from __future__ import print_function

from __future__ import absolute_import
from __future__ import unicode_literals
import re
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connections

from corehq.form_processor.utils.sql import fetchall_as_namedtuple
from corehq.sql_db.config import partition_config, parse_existing_shard, get_shards_to_update
from six.moves import input

SHARD_OPTION_RX = re.compile(r'^p[\d+]')

SERVER_TEMPLATE = """
    CREATE SERVER {server_name} FOREIGN DATA WRAPPER plproxy
    OPTIONS (
        connection_lifetime '1800',
        disable_binary '1',
        {partitions}
    );
"""

USER_MAPPING_TEMPLATE = """
    CREATE USER MAPPING FOR {USER} SERVER {server_name} OPTIONS (user '{USER}', password '{PASSWORD}');
"""

ALTER_SERVER_TEMPLATE = """
    ALTER SERVER {server_name} OPTIONS (
        {options}
    );
"""


class Command(BaseCommand):
    help = 'Creates or updates the pl_proxy cluster configuration'

    def add_arguments(self, parser):
        parser.add_argument(
            '--verbose',
            action='store_true',
            dest='verbose',
            default=False,
        )

    def handle(self, **options):
        if not settings.USE_PARTITIONED_DATABASE:
            print("System not configured to use a partitioned database")

        verbose = options['verbose']
        existing_config = _get_existing_cluster_config(settings.PL_PROXY_CLUSTER_NAME)
        if existing_config:
            if _confirm("Cluster configuration already exists. Are you sure you want to change it?"):
                _update_pl_proxy_cluster(existing_config, verbose)
        else:
            create_pl_proxy_cluster(verbose)


def _get_current_shards(existing_config):
    existing_shards = [
        parse_existing_shard(option)
        for option in existing_config.srvoptions if _is_shard_option(option)
    ]
    return existing_shards


def _is_shard_option(option):
    return SHARD_OPTION_RX.match(option)


def _update_pl_proxy_cluster(existing_config, verbose):
    existing_shards = _get_current_shards(existing_config)
    new_shard_configs = partition_config.get_shards()

    if verbose:
        print('{0} Existing config {0}'.format('-' * 42))
        print(existing_config)
        print('-' * 100)

    shards_to_update = get_shards_to_update(existing_shards, new_shard_configs)

    if not shards_to_update:
        print('No changes. Exiting.')
    else:
        print("Shards to update:")
        existing_shards_by_id = {shard.id: shard for shard in existing_shards}
        for new in shards_to_update:
            print("    {}  ->   {}".format(
                existing_shards_by_id[new.id].get_server_option_string(),
                new.get_server_option_string()
            ))
        if _confirm("Update these shards?"):
            alter_sql = _get_alter_server_sql(shards_to_update)
            if verbose:
                print(alter_sql)

            with connections[partition_config.get_proxy_db()].cursor() as cursor:
                cursor.execute(alter_sql)
        else:
            print('Abort')


def _get_alter_server_sql(shards_to_update):
    shard_option_template = "SET {}"
    shards_sql = []
    for shard in shards_to_update:
        shards_sql.append(shard_option_template.format(shard.get_server_option_string()))

    return ALTER_SERVER_TEMPLATE.format(
        server_name=settings.PL_PROXY_CLUSTER_NAME,
        options=',\n'.join(shards_sql)
    )


def create_pl_proxy_cluster(verbose=False, drop_existing=False):
    proxy_db = partition_config.get_proxy_db()

    if drop_existing:
        with connections[proxy_db].cursor() as cursor:
            cursor.execute(get_drop_server_sql())

    config_sql = get_pl_proxy_server_config_sql(partition_config.get_shards())
    user_mapping_sql = get_user_mapping_sql()

    if verbose:
        print('Running SQL')
        print(config_sql)
        print(user_mapping_sql)

    with connections[proxy_db].cursor() as cursor:
        cursor.execute(config_sql)
        cursor.execute(user_mapping_sql)


def get_drop_server_sql():
    return 'DROP SERVER IF EXISTS {} CASCADE;'.format(settings.PL_PROXY_CLUSTER_NAME)


def _get_existing_cluster_config(cluster_name):
    proxy_db = partition_config.get_proxy_db()
    with connections[proxy_db].cursor() as cursor:
        cursor.execute('SELECT * from pg_foreign_server where srvname = %s', [cluster_name])
        results = list(fetchall_as_namedtuple(cursor))
        if results:
            return results[0]


def get_pl_proxy_server_config_sql(shards):
    shard_configs_strings = [shard.get_server_option_string() for shard in shards]

    server_sql = SERVER_TEMPLATE.format(
        server_name=settings.PL_PROXY_CLUSTER_NAME,
        partitions=',\n'.join(shard_configs_strings)
    )

    return server_sql


def get_user_mapping_sql():
    proxy_db = partition_config.get_proxy_db()
    proxy_db_config = settings.DATABASES[proxy_db].copy()
    proxy_db_config['server_name'] = settings.PL_PROXY_CLUSTER_NAME
    return USER_MAPPING_TEMPLATE.format(**proxy_db_config)


def _confirm(msg):
    confirm_update = input(msg + ' [yes / no] ')
    return confirm_update == 'yes'
