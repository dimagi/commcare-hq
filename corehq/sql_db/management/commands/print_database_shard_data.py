from __future__ import absolute_import, print_function
from django.core.management.base import BaseCommand
from corehq.sql_db.shard_data_management import get_database_shard_info
from corehq.sql_db.util import get_db_aliases_for_partitioned_query


class Command(BaseCommand):
    help = "Print out all aggregate shard data in all databases"

    def handle(self, **options):
        for database in get_db_aliases_for_partitioned_query():
            shard_info = get_database_shard_info(database)
            print(shard_info)
