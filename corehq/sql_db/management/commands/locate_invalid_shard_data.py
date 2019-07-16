from __future__ import absolute_import, print_function, unicode_literals

import re
from datetime import datetime

from django.core.management.base import BaseCommand
from django.db import connections

from corehq.sql_db.shard_data_management import (
    delete_unmatched_shard_data,
    get_count_of_unmatched_models_by_shard,
)
from corehq.sql_db.util import (
    get_all_sharded_models,
    get_db_aliases_for_partitioned_query,
)
from corehq.util.log import with_progress_bar


class Command(BaseCommand):
    help = "Print out all shard data that exists in databases that don't contain the associated shards."

    def add_arguments(self, parser):
        parser.add_argument('--database', action='store')
        parser.add_argument('--model', action='store')
        parser.add_argument('--delete', action='store_true')

    def handle(self, **options):
        sharded_models = list(get_all_sharded_models())
        databases = [options.get('database')] or get_db_aliases_for_partitioned_query()
        for database in databases:
            for model in sharded_models:
                if options['model'] and options['model'] != model.__name__:
                    continue

                if options['delete']:
                    self.delete(database, model)
                else:
                    invalid_data = get_count_of_unmatched_models_by_shard(database, model)
                    if invalid_data:
                        for shard_id, count in invalid_data:
                            print('found {} unexpected {}s in {} (shard {}).'.format(
                                count, model.__name__, database, shard_id)
                            )

    def delete(self, database, model):
        print("{} Deleting invalid {} from database {}".format(datetime.utcnow(), model.__name__, database))

        # Use explain query to get an approximation of how many rows there are in the table
        number_to_delete = 0
        query = model.objects.using(database)
        sql, params = query.query.sql_with_params()
        explain_query = 'EXPLAIN {}'.format(sql)
        db_cursor = connections[database].cursor()
        with db_cursor as cursor:
            cursor.execute(explain_query, params)
            for row in cursor.fetchall():
                search = re.search(r' rows=(\d+)', row[0])
                if search:
                    number_to_delete = int(search.group(1))
                    break

        query_size = 10000
        length = (number_to_delete // query_size) + 1
        total_deleted = 0
        for value, num_deleted in with_progress_bar(
                delete_unmatched_shard_data(database, model, query_size=query_size),
                length=length, oneline=False):
            total_deleted += num_deleted
            print("All invalid values below {} are deleted, {} docs deleted so far".format(value, total_deleted))

        print("{} Deleted {} invalid {} from database {}".format(datetime.utcnow(), total_deleted, model.__name__, database))
