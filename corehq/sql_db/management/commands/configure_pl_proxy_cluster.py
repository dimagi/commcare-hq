from optparse import make_option

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connections

from corehq.form_processor.utils.sql import fetchall_as_namedtuple
from corehq.sql_db.config import PartitionConfig

SHARD_TEMPLATE = "p{SHARD_ID} 'dbname={NAME} host={HOST} port={PORT}'"

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
            confirm_update = raw_input("Cluster configuration already exists. Are you sure you want to change it?")
            if confirm_update == 'yes':
                create_pl_proxy_cluster(verbose, drop_existing=True)
        else:
            create_pl_proxy_cluster(verbose)


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


def cluster_exists(cluster_name):
    proxy_db = PartitionConfig().get_proxy_db()
    with connections[proxy_db].cursor() as cursor:
        cursor.execute('SELECT srvname from pg_foreign_server where srvname = %s', [cluster_name])
        result = fetchall_as_namedtuple(cursor)
        return bool(result)


def get_pl_proxy_server_config_sql(shards):
    shard_configs = get_shard_config_strings(shards)

    server_sql = SERVER_TEMPLATE.format(
        server_name=settings.PL_PROXY_CLUSTER_NAME,
        partitions=',\n'.join(shard_configs)
    )

    return server_sql


def get_user_mapping_sql():
    proxy_db = PartitionConfig().get_proxy_db()
    proxy_db_config = settings.DATABASES[proxy_db].copy()
    proxy_db_config['server_name'] = settings.PL_PROXY_CLUSTER_NAME
    return USER_MAPPING_TEMPLATE.format(**proxy_db_config)


def get_shard_config_strings(shards):
    from django.db.backends.creation import TEST_DATABASE_PREFIX

    shard_configs = []
    for shard in shards:
        db_config = settings.DATABASES[shard.db_name].copy()
        db_config['SHARD_ID'] = shard.shard_number
        if settings.UNIT_TESTING:
            db_config['NAME'] = TEST_DATABASE_PREFIX + db_config['NAME']
        shard_configs.append(
            SHARD_TEMPLATE.format(**db_config)
        )
    return shard_configs


