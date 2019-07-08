from __future__ import absolute_import, print_function, unicode_literals

from django.core.management.base import BaseCommand

from corehq.sql_db.shard_data_management import (
    delete_unmatched_shard_data,
    get_count_of_unmatched_models_by_shard,
)
from corehq.sql_db.util import (
    get_all_sharded_models,
    get_db_aliases_for_partitioned_query,
)


class Command(BaseCommand):
    help = "Print out all shard data that exists in databases that don't contain the associated shards."

    def add_arguments(self, parser):
        parser.add_argument('--delete', action='store_true')

    def handle(self, **options):
        sharded_models = list(get_all_sharded_models())
        for database in get_db_aliases_for_partitioned_query():
            for model in sharded_models:
                if options['delete']:
                    count = delete_unmatched_shard_data(database, model)
                    if count:
                        print('deleted {} {} from {}'.format(
                            count, model.__name__, database)
                        )
                else:
                    invalid_data = get_count_of_unmatched_models_by_shard(database, model)
                    if invalid_data:
                        for shard_id, count in invalid_data:
                            print('found {} unexpected {}s in {} (shard {}).'.format(
                                count, model.__name__, database, shard_id)
                            )
