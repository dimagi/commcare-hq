import re

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connections

from corehq.form_processor.utils.sql import fetchall_as_namedtuple
from corehq.sql_db.config import ShardMeta, plproxy_config, plproxy_standby_config

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

        verbose = options['verbose']
        create_or_update_cluster(plproxy_config, verbose, options['create_only'])
        create_or_update_cluster(plproxy_standby_config, verbose, options['create_only'])


def create_or_update_cluster(cluster_config, verbose, create_only):
    existing_config = _get_existing_cluster_config(cluster_config)
    if existing_config:
        if create_only:
            return
        if _confirm(f"Cluster configuration already exists on '{cluster_config.proxy_db}'."
                    f" Are you sure you want to change it?"):
            _update_pl_proxy_cluster(cluster_config, existing_config, verbose)
    else:
        create_pl_proxy_cluster(cluster_config, verbose)


def parse_existing_shard(shard_option):
    shard_name, options = shard_option.split('=', 1)
    assert shard_name[0] == 'p'
    shard_id = int(shard_name[1:])
    options = options.split(' ')
    option_kwargs = dict(tuple(option.split('=')) for option in options)
    if 'port' in option_kwargs:
        option_kwargs['port'] = int(option_kwargs['port'])
    return ShardMeta(id=shard_id, **option_kwargs)


def _get_current_shards(existing_config):
    existing_shards = [
        parse_existing_shard(option)
        for option in existing_config.srvoptions if _is_shard_option(option)
    ]
    return existing_shards


def _is_shard_option(option):
    return SHARD_OPTION_RX.match(option)


def _update_pl_proxy_cluster(cluster_config, existing_config, verbose):
    existing_shards = _get_current_shards(existing_config)
    new_shard_configs = cluster_config.get_shards()

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
            alter_sql = _get_alter_server_sql(cluster_config.cluster_name, shards_to_update)
            if verbose:
                print(alter_sql)

            with connections[cluster_config.proxy_db].cursor() as cursor:
                cursor.execute(alter_sql)
        else:
            print('Abort')


def _get_alter_server_sql(cluster_name, shards_to_update):
    shard_option_template = "SET {}"
    shards_sql = []
    for shard in shards_to_update:
        shards_sql.append(shard_option_template.format(shard.get_server_option_string()))

    return ALTER_SERVER_TEMPLATE.format(
        server_name=cluster_name,
        options=',\n'.join(shards_sql)
    )


def create_pl_proxy_cluster(cluster_config, verbose=False, drop_existing=False):
    proxy_db = cluster_config.proxy_db

    if drop_existing:
        with connections[proxy_db].cursor() as cursor:
            cursor.execute(get_drop_server_sql(cluster_config.cluster_name))

    config_sql = get_pl_proxy_server_config_sql(cluster_config.cluster_name, cluster_config.get_shards())
    user_mapping_sql = get_user_mapping_sql(cluster_config)

    if verbose:
        print('Running SQL')
        print(config_sql)
        print(user_mapping_sql)

    with connections[proxy_db].cursor() as cursor:
        cursor.execute(config_sql)
        cursor.execute(user_mapping_sql)


def get_drop_server_sql(cluster_name):
    return 'DROP SERVER IF EXISTS {} CASCADE;'.format(cluster_name)


def _get_existing_cluster_config(cluster_config):
    proxy_db = cluster_config.proxy_db
    with connections[proxy_db].cursor() as cursor:
        cursor.execute('SELECT * from pg_foreign_server where srvname = %s', [cluster_config.cluster_name])
        results = list(fetchall_as_namedtuple(cursor))
        if results:
            return results[0]


def get_pl_proxy_server_config_sql(cluster_name, shards):
    shard_configs_strings = [shard.get_server_option_string() for shard in shards]

    server_sql = SERVER_TEMPLATE.format(
        server_name=cluster_name,
        partitions=',\n'.join(shard_configs_strings)
    )

    return server_sql


def get_user_mapping_sql(cluster_config):
    proxy_db = cluster_config.proxy_db
    proxy_db_config = settings.DATABASES[proxy_db].copy()
    proxy_db_config['server_name'] = cluster_config.cluster_name
    return USER_MAPPING_TEMPLATE.format(**proxy_db_config)


def _confirm(msg):
    confirm_update = input(msg + ' [yes / no] ')
    return confirm_update == 'yes'


def get_shards_to_update(existing_shards, new_shards):
    assert len(existing_shards) == len(new_shards)
    shards_to_update = []
    for existing, new in zip(existing_shards, new_shards):
        assert existing.id == new.id, '{} != {}'.format(existing.id, new.id)
        if existing != new:
            shards_to_update.append(new)

    return shards_to_update
