from optparse import make_option

import re
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connections

from corehq.form_processor.utils.sql import fetchall_as_namedtuple
from corehq.sql_db.config import PartitionConfig, parse_existing_shard, get_shards_to_update

SHARD_OPTION_RX = re.compile('^p[\d+]')

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
    args = ''
    help = 'Creates or updates the pl_proxy cluster configuration'

    option_list = BaseCommand.option_list + (
        make_option('--verbose',
            action='store_true',
            dest='verbose',
            default=False),
        )

    def handle(self, *args, **options):
        if not settings.USE_PARTITIONED_DATABASE:
            print "System not configured to use a partitioned database"

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
    config = PartitionConfig()
    new_shard_configs = config.get_shards()

    shards_to_update = get_shards_to_update(existing_shards, new_shard_configs)

    if not shards_to_update:
        print 'No changes. Exiting.'
    else:
        print "Shards to update:"
        existing_shards_by_id = {shard.id: shard for shard in existing_shards}
        for new in shards_to_update:
            print "    {}  ->   {}".format(
                existing_shards_by_id[new.id].get_server_option_string(),
                new.get_server_option_string()
            )
        if _confirm("Update these shards?"):
            alter_sql = _get_alter_server_sql(shards_to_update)
            if verbose:
                print alter_sql

            with connections[config.get_proxy_db()].cursor() as cursor:
                cursor.execute(alter_sql)
        else:
            print 'Abort'


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
    config = PartitionConfig()
    proxy_db = config.get_proxy_db()

    if drop_existing:
        with connections[proxy_db].cursor() as cursor:
            cursor.execute(get_drop_server_sql())

    config_sql = get_pl_proxy_server_config_sql(config.get_shards())
    user_mapping_sql = get_user_mapping_sql()

    if verbose:
        print 'Running SQL'
        print config_sql
        print user_mapping_sql

    with connections[proxy_db].cursor() as cursor:
        cursor.execute(config_sql)
        cursor.execute(user_mapping_sql)


def get_drop_server_sql():
    return 'DROP SERVER IF EXISTS {} CASCADE;'.format(settings.PL_PROXY_CLUSTER_NAME)


def _get_existing_cluster_config(cluster_name):
    proxy_db = PartitionConfig().get_proxy_db()
    with connections[proxy_db].cursor() as cursor:
        cursor.execute('SELECT * from pg_foreign_server where srvname = %s', [cluster_name])
        results = fetchall_as_namedtuple(cursor)
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
    proxy_db = PartitionConfig().get_proxy_db()
    proxy_db_config = settings.DATABASES[proxy_db].copy()
    proxy_db_config['server_name'] = settings.PL_PROXY_CLUSTER_NAME
    return USER_MAPPING_TEMPLATE.format(**proxy_db_config)


def _confirm(msg):
    confirm_update = raw_input(msg + ' [yes / no] ')
    return confirm_update == 'yes'
