from optparse import make_option

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from corehq.form_processor.utils.sql import fetchall_as_namedtuple
from corehq.sql_db.config import PartitionConfig

SHARD_TEMPLATE = "p{SHARD_ID} 'dbname={NAME} hostname={HOST} port={PORT}'"

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


class Command(BaseCommand):
    args = ''
    help = 'Updates the pl_proxy cluster configuration'

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
        if cluster_exists(settings.PL_PROXY_CLUSTER_NAME):
            pass # prompt user to confirm and then drop
        else:
            create_pl_proxy_cluster(verbose)


def create_pl_proxy_cluster(verbose=False):
    config = PartitionConfig()
    proxy_db = config.get_proxy_db()
    config_sql = get_pl_proxy_server_config_sql(config.shard_mapping())

    proxy_db_config = settings.DATABASES[proxy_db].copy()
    proxy_db_config['server_name'] = settings.PL_PROXY_CLUSTER_NAME
    user_mapping_sql = USER_MAPPING_TEMPLATE.format(**proxy_db_config)

    if verbose:
        print 'Running SQL'
        print config_sql
        print user_mapping_sql

    with connection.cursor() as cursor:
        cursor.execute(config_sql)
        cursor.execute(user_mapping_sql)


def cluster_exists(cluster_name):
    with connection.cursor() as cursor:
        cursor.execute('SELECT srvname from pg_foreign_server where srvname = %s', [cluster_name])
        result = fetchall_as_namedtuple(cursor)
        return bool(result)


def get_pl_proxy_server_config_sql(shard_mapping):
    shard_configs = get_shard_config_strings(shard_mapping)

    server_sql = SERVER_TEMPLATE.format(
        server_name=settings.PL_PROXY_CLUSTER_NAME,
        partitions=',\n'.join(shard_configs)
    )

    return server_sql


def get_shard_config_strings(shard_mapping):
    shard_configs = []
    for shard_id in sorted(shard_mapping.keys()):
        django_db_name = shard_mapping[shard_id]
        db_config = settings.DATABASES[django_db_name].copy()
        db_config['SHARD_ID'] = shard_id
        shard_configs.append(
            SHARD_TEMPLATE.format(**db_config)
        )
    return shard_configs


