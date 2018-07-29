from __future__ import absolute_import, print_function
from __future__ import unicode_literals
from django.core.management.base import BaseCommand
from corehq.sql_db.shard_data_management import get_database_shard_info
from corehq.sql_db.util import get_db_aliases_for_partitioned_query


class Command(BaseCommand):
    help = "Print out all aggregate shard data in all databases"

    def add_arguments(self, parser):
        parser.add_argument(
            '--verbose',
            action='store_true',
            dest='verbose',
            default=False,
        )
        parser.add_argument(
            '--csv',
            action='store_true',
            dest='csv',
            default=False,
        )

    def handle(self, **options):
        verbose = options['verbose']
        csv_mode = options['csv']
        if csv_mode:
            print('shard_id,model_name,doc_count,valid/invalid')
        for database in get_db_aliases_for_partitioned_query():
            if verbose:
                print('Checking database {}...'.format(database))
            shard_info = get_database_shard_info(database)
            if options['csv']:
                print(shard_info.to_csv())
            else:
                print(shard_info)
