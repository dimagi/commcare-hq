import re

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connections

from corehq.form_processor.utils.sql import fetchall_as_namedtuple
from corehq.sql_db.config import (
    get_shards_to_update,
    parse_existing_shard,
    partition_config as primary_partition_config,
    standby_partition_config
)

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
        parser.add_argument(
            '--create_only',
            action='store_true',
            dest='create_only',
            default=False,
        )

    def handle(self, **options):
        if not settings.USE_PARTITIONED_DATABASE:
            print("System not configured to use a partitioned database")

        create_only = options['create_only']
        verbose = options['verbose']
        self.create_update_cluster(primary_partition_config, create_only, verbose)
        if standby_partition_config:
            self.create_update_cluster(standby_partition_config, create_only, verbose)

    def create_update_cluster(self, partition_config, create_only, verbose):
        existing_config = _get_existing_cluster_config(partition_config)
        if existing_config:
            if create_only:
                return
            name = partition_config.plproxy_cluster_name
            if _confirm(f"Configuration already exists for cluster {name}. Are you sure you want to change it?"):
                _update_pl_proxy_cluster(partition_config, existing_config, verbose)
        else:
            create_pl_proxy_cluster(partition_config, verbose)


def _get_current_shards(existing_config):
    existing_shards = [
        parse_existing_shard(option)
        for option in existing_config.srvoptions if _is_shard_option(option)
    ]
    return existing_shards


def _is_shard_option(option):
    return SHARD_OPTION_RX.match(option)


def _update_pl_proxy_cluster(partition_config, existing_config, verbose):
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
            alter_sql = _get_alter_server_sql(shards_to_update, partition_config.plproxy_cluster_name)
            if verbose:
                print(alter_sql)

            with connections[partition_config.get_proxy_db()].cursor() as cursor:
                cursor.execute(alter_sql)
        else:
            print('Abort')


def _get_alter_server_sql(shards_to_update, cluster_name):
    shard_option_template = "SET {}"
    shards_sql = []
    for shard in shards_to_update:
        shards_sql.append(shard_option_template.format(shard.get_server_option_string()))

    return ALTER_SERVER_TEMPLATE.format(
        server_name=cluster_name,
        options=',\n'.join(shards_sql)
    )


def create_pl_proxy_cluster(partition_config, verbose=False, drop_existing=False):
    proxy_db = partition_config.get_proxy_db()

    if drop_existing:
        with connections[proxy_db].cursor() as cursor:
            cursor.execute(get_drop_server_sql(partition_config.plproxy_cluster_name))

    config_sql = get_pl_proxy_server_config_sql(partition_config)
    user_mapping_sql = get_user_mapping_sql(partition_config)

    if verbose:
        print('Running SQL')
        print(config_sql)
        print(user_mapping_sql)

    with connections[proxy_db].cursor() as cursor:
        cursor.execute(config_sql)
        cursor.execute(user_mapping_sql)


def get_drop_server_sql(cluster_name):
    return 'DROP SERVER IF EXISTS {} CASCADE;'.format(cluster_name)


def _get_existing_cluster_config(partition_config):
    proxy_db = partition_config.get_proxy_db()
    with connections[proxy_db].cursor() as cursor:
        cursor.execute(
            'SELECT * from pg_foreign_server where srvname = %s',
            [partition_config.plproxy_cluster_name]
        )
        results = list(fetchall_as_namedtuple(cursor))
        if results:
            return results[0]


def get_pl_proxy_server_config_sql(partition_config):
    shard_configs_strings = [shard.get_server_option_string() for shard in partition_config.get_shards()]

    server_sql = SERVER_TEMPLATE.format(
        server_name=partition_config.plproxy_cluster_name,
        partitions=',\n'.join(shard_configs_strings)
    )

    return server_sql


def get_user_mapping_sql(partition_config):
    proxy_db = partition_config.get_proxy_db()
    proxy_db_config = settings.DATABASES[proxy_db].copy()
    proxy_db_config['server_name'] = partition_config.plproxy_cluster_name
    return USER_MAPPING_TEMPLATE.format(**proxy_db_config)


def _confirm(msg):
    confirm_update = input(msg + ' [yes / no] ')
    return confirm_update == 'yes'
